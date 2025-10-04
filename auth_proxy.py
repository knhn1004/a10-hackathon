#!/usr/bin/env python3
"""
Per-User MCP Process Manager & Auth Proxy.

For each user, spawns an isolated mcpo instance with their own environment variables.
Maintains a mapping of user sessions to mcpo instances.

Architecture:
    User -> Auth Proxy (port 8000)
            -> Validates token with dashboard
            -> Spawns/routes to user-specific mcpo (dynamic port)
                -> mcpo launches mcp_server.py with user's MCP_API_TOKEN

Usage:
    python auth_proxy.py
"""
import asyncio
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8080")
PROXY_HOST = os.getenv("PROXY_HOST", "0.0.0.0")  # Host to bind to
PROXY_PORT = int(os.getenv("PROXY_PORT", "8001"))  # Port to bind to
BASE_PORT = 9000  # Start allocating ports from here
MCPO_TIMEOUT = 30  # Timeout for mcpo startup
IDLE_TIMEOUT = 3600  # Kill idle mcpo after 1 hour

app = FastAPI(title="MCP Auth Proxy & Process Manager")


@dataclass
class McpoInstance:
    """Represents a running mcpo instance for a user."""

    user_id: str
    token: str
    port: int
    process: subprocess.Popen
    created_at: float
    last_accessed: float

    def is_alive(self) -> bool:
        """Check if process is still running."""
        return self.process.poll() is None

    def terminate(self):
        """Gracefully terminate the mcpo process and all its children."""
        if self.is_alive():
            logger.info(
                f"🔴 Terminating mcpo for user {self.user_id} (port {self.port})"
            )

            # Kill entire process group to clean up all children
            import os
            import signal

            pgid = None
            try:
                # Get the process group ID
                pgid = os.getpgid(self.process.pid)
                # Send SIGTERM to the entire process group
                os.killpg(pgid, signal.SIGTERM)
                logger.debug(f"Sent SIGTERM to process group {pgid}")
            except (ProcessLookupError, PermissionError) as e:
                logger.debug(f"Could not kill process group, trying direct kill: {e}")
                self.process.terminate()

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing mcpo for user {self.user_id}")
                try:
                    if pgid:
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        self.process.kill()
                except:
                    self.process.kill()


# Global state: token -> McpoInstance (one mcpo per unique token)
token_sessions: Dict[str, McpoInstance] = {}
used_ports = set()
session_lock = asyncio.Lock()

# Public mcpo instance for OpenAPI spec (no auth required)
public_mcpo: Optional[McpoInstance] = None


# Add exception handler for HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensure HTTPException returns JSON."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

http_client = httpx.AsyncClient(timeout=30.0)


def allocate_port() -> int:
    """
    Allocate an available high port by actually checking if it's free.
    Uses socket binding to ensure port is truly available.
    """
    import socket

    # Start from a high port to avoid conflicts
    for attempt in range(100):  # Try 100 ports
        port = BASE_PORT + attempt

        # Skip if we think it's in use
        if port in used_ports:
            continue

        # Actually test if the port is free
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", port))
                # Port is free!
                used_ports.add(port)
                return port
        except OSError:
            # Port is in use, try next
            continue

    # If we get here, we couldn't find a free port
    raise RuntimeError(f"Could not find free port in range {BASE_PORT}-{BASE_PORT+100}")


def release_port(port: int):
    """Release a port back to the pool."""
    used_ports.discard(port)


async def spawn_mcpo_for_user(user_id: str, token: str) -> McpoInstance:
    """
    Spawn a new mcpo instance for a user with their environment variables.

    Args:
        user_id: The user's ID
        token: The user's API token (used as MCP_API_TOKEN in mcp_server)

    Returns:
        McpoInstance with process details
    """
    port = allocate_port()

    # Find uvx executable
    uvx_path = shutil.which("uvx")
    if not uvx_path:
        raise RuntimeError("uvx not found in PATH")

    # Prepare environment variables for the mcp_server
    env = os.environ.copy()
    env["MCP_API_TOKEN"] = token  # Pass the user's token to mcp_server
    env["USER_ID"] = user_id
    env["DASHBOARD_URL"] = DASHBOARD_URL

    # Determine if we should use poetry or python directly
    # Check for poetry in PATH and pyproject.toml in current directory
    cwd = os.path.dirname(os.path.abspath(__file__))
    poetry_path = shutil.which("poetry")
    use_poetry = poetry_path and os.path.exists(os.path.join(cwd, "pyproject.toml"))

    # Spawn mcpo process
    if use_poetry:
        # Command: uvx mcpo --port {port} -- poetry run python mcp_server.py
        cmd = [
            uvx_path,
            "mcpo",
            "--port",
            str(port),
            "--",
            "poetry",
            "run",
            "python",
            "mcp_server.py",
        ]
    else:
        # Command: uvx mcpo --port {port} -- python mcp_server.py
        cmd = [uvx_path, "mcpo", "--port", str(port), "--", "python", "mcp_server.py"]

    logger.info(f"🚀 Spawning mcpo for user {user_id} on port {port}")
    logger.info(f"   Command: {' '.join(cmd)}")
    logger.info(f"   Using Poetry: {use_poetry}")

    try:
        # Start in a new process group so we can kill all children
        # Use devnull for stdout/stderr to prevent pipe buffer filling and hanging
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,  # Create new process group
        )

        # Wait for mcpo to be ready
        backend_url = f"http://localhost:{port}"
        start_time = time.time()

        while time.time() - start_time < MCPO_TIMEOUT:
            if process.poll() is not None:
                # Process died
                stdout, stderr = process.communicate()
                logger.error(f"❌ mcpo process died for user {user_id}")
                logger.error(f"STDOUT: {stdout.decode()}")
                logger.error(f"STDERR: {stderr.decode()}")
                release_port(port)
                raise RuntimeError(f"mcpo process failed to start: {stderr.decode()}")

            # Check if mcpo is responding
            try:
                response = await http_client.get(
                    f"{backend_url}/openapi.json", timeout=2.0
                )
                if response.status_code == 200:
                    logger.info(f"✅ mcpo ready for user {user_id} on port {port}")
                    break
            except:
                pass

            await asyncio.sleep(0.5)
        else:
            # Timeout
            logger.error(f"❌ mcpo startup timeout for user {user_id}")
            process.kill()
            release_port(port)
            raise RuntimeError(f"mcpo failed to start within {MCPO_TIMEOUT}s")

        return McpoInstance(
            user_id=user_id,
            token=token,
            port=port,
            process=process,
            created_at=time.time(),
            last_accessed=time.time(),
        )

    except Exception as e:
        release_port(port)
        raise


async def check_mcpo_health(instance: McpoInstance) -> bool:
    """Check if mcpo instance is responsive (not just alive)."""
    try:
        response = await asyncio.wait_for(
            http_client.get(f"http://localhost:{instance.port}/openapi.json"),
            timeout=2.0,
        )
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Health check failed for port {instance.port}: {e}")
        return False


async def get_or_create_mcpo(user_id: str, token: str) -> McpoInstance:
    """
    Get existing mcpo instance for token or create a new one.
    Each unique token gets its own isolated mcpo process.
    Thread-safe with async lock.
    """
    async with session_lock:
        # Check if this token already has an mcpo instance
        if token in token_sessions:
            instance = token_sessions[token]

            # Check if it's still alive AND responsive
            if instance.is_alive():
                # Quick health check to detect hung processes
                is_healthy = await check_mcpo_health(instance)
                if is_healthy:
                    # Update last accessed time
                    instance.last_accessed = time.time()
                    logger.info(
                        f"♻️  Reusing existing mcpo for user {user_id} on port {instance.port}"
                    )
                    return instance
                else:
                    # Process is alive but hung, force restart
                    logger.warning(
                        f"🚨 mcpo for token {token[:16]}... is hung (alive but not responding), restarting"
                    )
                    instance.terminate()
                    release_port(instance.port)
                    del token_sessions[token]
            else:
                # Process died, clean up
                logger.warning(f"⚠️  mcpo for token {token[:16]}... died, respawning")
                release_port(instance.port)
                del token_sessions[token]

        # Create new mcpo instance for this token
        instance = await spawn_mcpo_for_user(user_id, token)
        token_sessions[token] = instance
        return instance


async def cleanup_idle_sessions():
    """Background task to clean up idle mcpo instances."""
    while True:
        await asyncio.sleep(60)  # Check every minute

        async with session_lock:
            now = time.time()
            to_remove = []

            for token, instance in token_sessions.items():
                idle_time = now - instance.last_accessed

                if idle_time > IDLE_TIMEOUT:
                    logger.info(
                        f"🧹 Cleaning up idle session for user {instance.user_id} (idle for {idle_time:.0f}s)"
                    )
                    instance.terminate()
                    release_port(instance.port)
                    to_remove.append(token)

            for token in to_remove:
                del token_sessions[token]


async def validate_token(token: str) -> dict:
    """Validate token against dashboard."""
    try:
        response = await http_client.post(
            f"{DASHBOARD_URL}/api/tokens/validate",
            params={"token": token},
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("valid"):
                return data
        return {"valid": False}
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"valid": False}


@app.middleware("http")
async def auth_and_proxy(request: Request, call_next):
    """Validate token, spawn/get user's mcpo instance, and proxy request."""

    # Handle OPTIONS preflight globally (CORS requires no auth for OPTIONS)
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "3600",
            },
        )

    # Public endpoints (no auth required)
    PUBLIC_PATHS = [
        "/",
        "/proxy-health",
        "/admin/sessions",
        "/openapi.json",
        "/docs",
        "/redoc",
    ]

    if request.url.path in PUBLIC_PATHS:
        if request.url.path == "/":
            # Root status endpoint
            async with session_lock:
                session_count = len(token_sessions)

            # Generate connection URLs for different environments
            localhost_url = f"http://localhost:{PROXY_PORT}"
            docker_url = f"http://host.docker.internal:{PROXY_PORT}"
            network_url = (
                f"http://{PROXY_HOST}:{PROXY_PORT}" if PROXY_HOST != "0.0.0.0" else None
            )

            return JSONResponse(
                content={
                    "service": "MCP Auth Proxy & Process Manager",
                    "status": "ok",
                    "version": "1.0.0",
                    "active_token_sessions": session_count,
                    "public_mcpo": (
                        "running"
                        if (public_mcpo and public_mcpo.is_alive())
                        else "unavailable"
                    ),
                    "connection_urls": {
                        "localhost": localhost_url,
                        "docker_containers": docker_url,
                        "network": network_url,
                    },
                    "endpoints": {
                        "health": "/proxy-health",
                        "openapi": "/openapi.json",
                        "admin": "/admin/sessions",
                    },
                    "configuration": {
                        "dashboard_url": DASHBOARD_URL,
                        "proxy_host": PROXY_HOST,
                        "proxy_port": PROXY_PORT,
                        "base_mcpo_port": BASE_PORT,
                    },
                }
            )

        if request.url.path == "/proxy-health":
            # Return health status with session count
            async with session_lock:
                session_count = len(token_sessions)
            return JSONResponse(
                content={"status": "ok", "active_sessions": session_count}
            )

        if request.url.path == "/admin/sessions":
            # Let the endpoint handler process this
            return await call_next(request)

        if request.url.path == "/openapi.json":
            # Forward to public mcpo instance
            if public_mcpo and public_mcpo.is_alive():
                try:
                    backend_url = f"http://localhost:{public_mcpo.port}/openapi.json"
                    backend_response = await http_client.get(backend_url, timeout=5.0)

                    # Add no-cache and CORS headers
                    headers = dict(backend_response.headers)
                    headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                    headers["Pragma"] = "no-cache"
                    headers["Expires"] = "0"
                    headers["Access-Control-Allow-Origin"] = "*"
                    headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                    headers["Access-Control-Allow-Headers"] = "*"

                    return Response(
                        content=backend_response.content,
                        status_code=backend_response.status_code,
                        headers=headers,
                    )
                except Exception as e:
                    logger.error(f"Error fetching OpenAPI spec from public mcpo: {e}")
                    return JSONResponse(
                        status_code=503,
                        content={"detail": "OpenAPI spec temporarily unavailable"},
                    )
            else:
                return JSONResponse(
                    status_code=503, content={"detail": "Public mcpo not available"}
                )

        # For other docs endpoints
        if request.url.path in ["/docs", "/redoc"]:
            return JSONResponse(
                status_code=404, content={"detail": "Use /openapi.json for API spec"}
            )

    # Protected endpoints - require auth and route to user's mcpo
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        logger.warning(f"Missing Bearer token for {request.url.path}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing Bearer token"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    token = auth.replace("Bearer ", "")

    # Validate token
    validation = await validate_token(token)
    if not validation.get("valid"):
        logger.warning(f"Invalid token for {request.url.path}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    user_id = validation.get("user_id", "unknown")
    logger.info(f"✅ {user_id} → {request.method} {request.url.path}")

    # Get or create mcpo instance for this user
    try:
        mcpo = await get_or_create_mcpo(user_id, token)
    except Exception as e:
        logger.error(f"Failed to spawn mcpo for user {user_id}: {e}")
        return JSONResponse(
            status_code=503,
            content={"detail": f"Failed to create session: {str(e)}"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    # Forward request to user's specific mcpo instance
    backend_url = f"http://localhost:{mcpo.port}"
    url = f"{backend_url}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"

    try:
        # Forward request to user's mcpo
        backend_response = await http_client.request(
            method=request.method,
            url=url,
            headers=dict(request.headers),
            content=await request.body(),
            timeout=60.0,  # Allow longer timeout for MCP operations
        )

        # Return backend response with CORS headers
        # Remove any CORS headers from backend to avoid duplicates
        response_headers = dict(backend_response.headers)
        response_headers.pop("access-control-allow-origin", None)
        response_headers.pop("access-control-allow-methods", None)
        response_headers.pop("access-control-allow-headers", None)
        response_headers.pop("access-control-allow-credentials", None)
        response_headers.pop("access-control-max-age", None)

        # Add our CORS headers (single source of truth)
        response_headers["Access-Control-Allow-Origin"] = "*"
        response_headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response_headers["Access-Control-Allow-Headers"] = "*"

        return Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=response_headers,
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout forwarding to mcpo for user {user_id}")
        return JSONResponse(
            status_code=504,
            content={"detail": "Backend timeout"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )
    except Exception as e:
        logger.error(f"Error forwarding to mcpo for user {user_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=502,
            content={"detail": f"Backend unavailable: {str(e) or type(e).__name__}"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )


async def spawn_public_mcpo() -> McpoInstance:
    """
    Spawn a public mcpo instance for serving OpenAPI spec.
    This runs without user-specific credentials.
    """
    global public_mcpo

    logger.info("🌐 Spawning public mcpo instance for OpenAPI spec")
    # Use a dummy token for the public instance
    public_mcpo = await spawn_mcpo_for_user("__public__", "public-readonly-token")
    return public_mcpo


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup."""
    logger.info("🚀 Starting background cleanup task")
    asyncio.create_task(cleanup_idle_sessions())

    # Spawn public mcpo for OpenAPI spec
    try:
        await spawn_public_mcpo()
        logger.info(f"✅ Public mcpo ready on port {public_mcpo.port}")
    except Exception as e:
        logger.error(f"❌ Failed to spawn public mcpo: {e}")
        logger.warning("⚠️  OpenAPI spec will not be available")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all mcpo instances on shutdown."""
    logger.info("🛑 Shutting down, terminating all mcpo instances")

    # Terminate public mcpo
    if public_mcpo and public_mcpo.is_alive():
        public_mcpo.terminate()
        release_port(public_mcpo.port)

    # Terminate user mcpo instances
    async with session_lock:
        for token, instance in token_sessions.items():
            instance.terminate()
            release_port(instance.port)
        token_sessions.clear()


@app.get("/admin/sessions")
async def list_sessions():
    """Admin endpoint to list all active sessions."""
    async with session_lock:
        sessions = []
        for token, instance in token_sessions.items():
            sessions.append(
                {
                    "user_id": instance.user_id,
                    "token_prefix": token[:16] + "...",
                    "port": instance.port,
                    "alive": instance.is_alive(),
                    "created_at": instance.created_at,
                    "last_accessed": instance.last_accessed,
                    "idle_seconds": time.time() - instance.last_accessed,
                }
            )
        return {"sessions": sessions}


if __name__ == "__main__":
    import uvicorn

    logger.info("🛡️  Starting Per-User MCP Process Manager & Auth Proxy")
    logger.info(f"   Dashboard: {DASHBOARD_URL}")
    logger.info(f"   Base port for mcpo instances: {BASE_PORT}")
    logger.info(f"   Idle timeout: {IDLE_TIMEOUT}s")
    logger.info(f"   Proxy listening on: http://{PROXY_HOST}:{PROXY_PORT}")
    logger.info("")
    logger.info("   Connection URLs:")
    logger.info(f"   - Local:        http://localhost:{PROXY_PORT}")
    logger.info(f"   - Docker:       http://host.docker.internal:{PROXY_PORT}")
    logger.info("")
    logger.info("   Each user gets their own isolated mcpo instance")
    logger.info("   with their token passed as MCP_API_TOKEN")

    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT)
