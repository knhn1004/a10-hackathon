#!/usr/bin/env python3
"""
Observability Dashboard Server

Provides a web-based dashboard for monitoring Docker containers with:
- Real-time metrics visualization
- Container resource utilization
- Historical data charts
- Container inspection
"""

import asyncio
import logging
import subprocess
import time
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uvicorn
import httpx
import os
import json

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv

from monitor import get_monitor, ContainerMonitor
from database.prisma_client import get_prisma
import token_manager_prisma as token_manager

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# Global monitor instance
monitor: Optional[ContainerMonitor] = None


async def check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def start_ollama():
    """Start Ollama server in the background."""
    try:
        logger.info("🤖 Starting Ollama server...")

        # Start Ollama serve in background
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent
        )

        # Wait a bit for it to start
        await asyncio.sleep(2)

        # Check if it's running
        if await check_ollama_running():
            logger.info("✅ Ollama server started successfully")
            return True
        else:
            logger.warning("⚠️  Ollama started but not responding yet")
            return False

    except FileNotFoundError:
        logger.warning("⚠️  Ollama not installed - LLM code filter will be disabled")
        logger.warning("   Install with: curl -fsSL https://ollama.com/install.sh | sh")
        return False
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False


async def ensure_ollama_model():
    """Ensure llama3.1 model is pulled."""
    try:
        logger.info("🤖 Checking for llama3.1:latest model...")

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                if "llama3.1:latest" in model_names:
                    logger.info("✅ llama3.1:latest model available")
                    return True
                else:
                    logger.warning("⚠️  llama3.1:latest not found")
                    logger.warning("   Pull with: ollama pull llama3.1:latest")
                    return False
    except Exception as e:
        logger.debug(f"Could not check Ollama models: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global monitor

    # Startup: Initialize and start monitoring
    logger.info("Starting dashboard server on http://0.0.0.0:8080")

    # Try to start Ollama for LLM code filtering
    if not await check_ollama_running():
        logger.info("🤖 Ollama not running, attempting to start...")
        await start_ollama()
    else:
        logger.info("✅ Ollama already running")

    # Check for required model
    if await check_ollama_running():
        await ensure_ollama_model()

    # Initialize monitor
    monitor = get_monitor()

    # Start monitoring in background
    monitoring_task = asyncio.create_task(monitor.start_monitoring())
    logger.info("Dashboard server started, monitoring active")

    yield  # Server is running

    # Shutdown: Cancel monitoring
    logger.info("Shutting down monitoring...")
    monitoring_task.cancel()
    try:
        await monitoring_task
    except asyncio.CancelledError:
        pass


# Create FastAPI app with lifespan
app = FastAPI(
    title="Code Sandbox Observability Dashboard",
    description="Real-time monitoring and observability for Docker-based code sandboxes",
    version="1.0.0",
    lifespan=lifespan,
)

# Add session middleware for OAuth
SESSION_SECRET = os.environ.get("SESSION_SECRET", "change-me-in-production-please")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OAuth
oauth = OAuth()

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
ENABLE_AUTH = os.environ.get("ENABLE_AUTH", "false").lower() == "true"

if ENABLE_AUTH and GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
    oauth.register(
        name='github',
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        authorize_url='https://github.com/login/oauth/authorize',
        authorize_params={'scope': 'user:email'},
        access_token_url='https://github.com/login/oauth/access_token',
        access_token_params=None,
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )
    logger.info("🔐 GitHub OAuth enabled")
else:
    if ENABLE_AUTH:
        logger.warning("⚠️  AUTH enabled but GitHub credentials missing - auth will not work!")
    else:
        logger.info("🔓 Authentication disabled (set ENABLE_AUTH=true to enable)")


# Authentication dependency
async def get_current_user(request: Request):
    """Get current authenticated user from session."""
    if not ENABLE_AUTH:
        # Auth disabled - allow all requests
        return {"login": "development-user", "email": "dev@localhost"}
    
    user = request.session.get('user')
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Public routes (no auth required)
# When ENABLE_AUTH is true, only protect token management endpoints
# All monitoring/observability endpoints remain public
PUBLIC_ROUTES = [
    "/", 
    "/auth/github", 
    "/auth/callback", 
    "/health", 
    "/api/health", 
    "/api/auth/me",
    "/api/overview",
    "/api/system",
    "/api/containers",
    "/api/requests/history",
    "/api/ml/",
    "/api/llm/",
    "/api/crashes",
    "/api/alerts",
]


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require authentication only for token management endpoints.
    
    Monitoring and observability endpoints are public.
    Only token generation/management requires authentication.
    """
    # Skip auth if disabled
    if not ENABLE_AUTH:
        return await call_next(request)
    
    # Check if route is public
    for public_route in PUBLIC_ROUTES:
        if request.url.path.startswith(public_route):
            return await call_next(request)
    
    # Only protect /api/tokens/* endpoints (require auth to manage tokens)
    if request.url.path.startswith("/api/tokens"):
        try:
            user_in_session = 'user' in request.session
        except (AssertionError, RuntimeError):
            user_in_session = False
        
        if not user_in_session:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated. Please login to manage API tokens."}
            )
    
    return await call_next(request)


# OAuth routes (no separate login page - button is on dashboard)

@app.get("/login")
async def login_redirect():
    """Redirect /login to dashboard (for backward compatibility)."""
    return RedirectResponse(url="/")


@app.get("/auth/github")
async def auth_github(request: Request):
    """Initiate GitHub OAuth flow."""
    if not ENABLE_AUTH:
        return RedirectResponse(url="/")
    
    redirect_uri = request.url_for('auth_callback')
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle GitHub OAuth callback.
    
    This must match your GitHub OAuth App settings:
    - For local dev: http://localhost:8080/auth/callback
    - For production: https://your-app.fly.dev/auth/callback
    """
    if not ENABLE_AUTH:
        return RedirectResponse(url="/")
    
    try:
        token = await oauth.github.authorize_access_token(request)
        resp = await oauth.github.get('user', token=token)
        user_info = resp.json()
        
        # Store user info in session
        request.session['user'] = {
            'login': user_info.get('login'),
            'name': user_info.get('name'),
            'email': user_info.get('email'),
            'avatar_url': user_info.get('avatar_url'),
        }
        
        logger.info(f"✅ User {user_info.get('login')} authenticated successfully")
        
        return RedirectResponse(url='/')
    except OAuthError as e:
        logger.error(f"OAuth error: {e}")
        return HTMLResponse(
            content=f"<h1>Authentication failed</h1><p>{str(e)}</p><a href='/login'>Try again</a>",
            status_code=400
        )


@app.get("/logout")
async def logout(request: Request):
    """Logout user and redirect to dashboard (which will show login button)."""
    request.session.clear()
    return RedirectResponse(url='/')


@app.get("/api/auth/me")
async def get_current_user_info(request: Request):
    """Get current authenticated user info.
    
    Returns user info from session or 401 if not authenticated.
    """
    if not ENABLE_AUTH:
        return {
            "authenticated": False,
            "auth_enabled": False,
            "user": None
        }
    
    user = request.session.get('user')
    if user:
        return {
            "authenticated": True,
            "auth_enabled": True,
            "user": user
        }
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")


# =============================================================================
# API Token Management Endpoints
# =============================================================================

class TokenGenerateRequest(BaseModel):
    name: str
    description: str = ""

@app.post("/api/tokens/generate")
async def generate_token_endpoint(
    token_request: TokenGenerateRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Generate a new API token for MCP authentication.
    
    Args:
        token_request: Token name and description
        user: Current authenticated user
    """
    user_id = user.get("login")
    github_id = user.get("id", user_id)  # Use GitHub numeric ID if available
    
    # Generate token using Prisma
    token = await token_manager.generate_token(
        str(github_id), 
        user_id, 
        token_request.name, 
        token_request.description
    )
    
    logger.info(f"🔑 Generated API token '{token_request.name}' for user {user_id}")
    
    return {
        "success": True,
        "token": token,
        "message": "Token generated successfully. Copy it now - you won't see it again!",
        "usage_instructions": {
            "mcp_server": "Set environment variable: MCP_API_TOKEN=<token>",
            "command_line": f"export MCP_API_TOKEN={token}"
        }
    }


@app.get("/api/tokens")
async def list_tokens(request: Request, user: dict = Depends(get_current_user)):
    """List all API tokens for current user."""
    github_id = str(user.get("id", user.get("login")))
    
    tokens = await token_manager.list_tokens(github_id)
    
    return {
        "tokens": tokens,
        "count": len(tokens)
    }


@app.post("/api/tokens/{token_id}/revoke")
async def revoke_token_endpoint(
    request: Request,
    token_id: str,
    user: dict = Depends(get_current_user)
):
    """Revoke an API token."""
    github_id = str(user.get("id", user.get("login")))
    
    success = await token_manager.revoke_token(github_id, token_id)
    
    if success:
        logger.info(f"🔒 Revoked API token for user {user.get('login')}")
        return {"success": True, "message": "Token revoked successfully"}
    else:
        raise HTTPException(status_code=404, detail="Token not found or unauthorized")


@app.delete("/api/tokens/{token_id}")
async def delete_token_endpoint(
    request: Request,
    token_id: str,
    user: dict = Depends(get_current_user)
):
    """Permanently delete an API token."""
    github_id = str(user.get("id", user.get("login")))
    
    success = await token_manager.delete_token(github_id, token_id)
    
    if success:
        logger.info(f"🗑️  Deleted API token for user {user.get('login')}")
        return {"success": True, "message": "Token deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Token not found or unauthorized")


@app.post("/api/tokens/validate")
async def validate_token_endpoint(token: str):
    """Validate an API token (used by MCP server).
    
    This is a PUBLIC endpoint called by users' local MCP servers.
    Each user's MCP server sends their personal token for validation.
    
    Args:
        token: The user's personal API token (from their local environment)
    """
    token_data = await token_manager.validate_token(token)
    
    if token_data:
        return {
            "valid": True,
            "user_id": token_data.get("user_id"),
            "token_name": token_data.get("name"),
        }
    else:
        return {
            "valid": False,
            "error": "Invalid or revoked token"
        }


# No middleware - we'll read MCP requests from file instead


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the dashboard HTML."""
    with open("dashboard.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "observability-dashboard",
        "monitoring_active": monitor is not None,
    }


@app.get("/api/system")
async def get_system_metrics(limit: int = 60):
    """
    Get system-wide metrics.

    Args:
        limit: Number of historical data points to return (default: 60)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    metrics = monitor.get_system_metrics(limit=limit)

    return {"metrics": metrics, "count": len(metrics)}


@app.get("/api/containers")
async def get_all_containers():
    """Get latest metrics for all containers."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    metrics = monitor.get_all_container_metrics()

    return {"containers": metrics, "count": len(metrics)}


@app.get("/api/containers/{container_id}")
async def get_container_metrics(container_id: str, limit: int = 60):
    """
    Get historical metrics for a specific container.

    Args:
        container_id: Container ID (short or full)
        limit: Number of historical data points to return (default: 60)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    metrics = monitor.get_container_metrics(container_id, limit=limit)

    if not metrics:
        raise HTTPException(
            status_code=404, detail="Container not found or no metrics available"
        )

    return {"container_id": container_id, "metrics": metrics, "count": len(metrics)}


@app.get("/api/containers/{container_id}/inspect")
async def inspect_container(container_id: str):
    """
    Get detailed container information via docker inspect.

    Args:
        container_id: Container ID (short or full)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    details = monitor.get_container_details(container_id)

    if not details:
        raise HTTPException(status_code=404, detail="Container not found")

    return details


@app.get("/api/containers/{container_id}/stats/summary")
async def get_container_stats_summary(container_id: str):
    """
    Get statistical summary for a container (min, max, avg).

    Args:
        container_id: Container ID (short or full)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    metrics = monitor.get_container_metrics(container_id, limit=300)

    if not metrics:
        raise HTTPException(
            status_code=404, detail="Container not found or no metrics available"
        )

    # Calculate statistics
    cpu_values = [m["cpu_percent"] for m in metrics]
    memory_values = [m["memory_usage_mb"] for m in metrics]
    memory_percent_values = [m["memory_percent"] for m in metrics]

    def calc_stats(values):
        if not values:
            return {"min": 0, "max": 0, "avg": 0}
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2),
        }

    return {
        "container_id": container_id,
        "sample_count": len(metrics),
        "cpu_percent": calc_stats(cpu_values),
        "memory_usage_mb": calc_stats(memory_values),
        "memory_percent": calc_stats(memory_percent_values),
        "latest": metrics[-1] if metrics else None,
    }


@app.get("/api/overview")
async def get_overview():
    """Get a comprehensive overview of all containers and system."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    # Get latest system metrics
    system_metrics = monitor.get_system_metrics(limit=1)
    latest_system = system_metrics[-1] if system_metrics else None

    # Get all containers with their latest metrics
    all_containers = monitor.get_all_container_metrics()

    # Build container summaries
    container_summaries = []
    for container_id, metrics_list in all_containers.items():
        if metrics_list:
            latest = metrics_list[-1]

            # Get historical stats
            history = monitor.get_container_metrics(container_id, limit=60)
            cpu_avg = (
                sum(m["cpu_percent"] for m in history) / len(history) if history else 0
            )

            container_summaries.append(
                {
                    "id": container_id,
                    "name": latest["name"],
                    "status": latest["status"],
                    "cpu_percent": latest["cpu_percent"],
                    "cpu_avg_1m": round(cpu_avg, 2),
                    "memory_usage_mb": latest["memory_usage_mb"],
                    "memory_percent": latest["memory_percent"],
                    "uptime": latest["timestamp"] - latest["created_at"],
                    "image": latest["image"],
                }
            )

    # Sort by CPU usage
    container_summaries.sort(key=lambda x: x["cpu_percent"], reverse=True)

    # Get crash history
    recent_crashes = monitor.get_crash_history(limit=10)

    return {
        "system": latest_system,
        "containers": container_summaries,
        "summary": {
            "total_containers": len(all_containers),
            "running_containers": sum(
                1 for c in container_summaries if c["status"] == "running"
            ),
            "total_cpu_percent": sum(c["cpu_percent"] for c in container_summaries),
            "total_memory_mb": sum(c["memory_usage_mb"] for c in container_summaries),
        },
        "recent_crashes": recent_crashes,
    }


@app.get("/api/crashes")
async def get_crashes(limit: int = 50):
    """Get crash history."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    crashes = monitor.get_crash_history(limit=limit)

    return {"crashes": crashes, "count": len(crashes)}


@app.get("/api/containers/{container_id}/crash")
async def get_container_crash(container_id: str):
    """Get crash information for a specific container."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    crash = monitor.get_crash_by_container(container_id)

    if not crash:
        raise HTTPException(status_code=404, detail="No crash found for this container")

    return crash


@app.get("/api/alerts")
async def get_network_alerts(limit: int = 50):
    """
    Get network and security alerts.

    Includes:
    - High network rate alerts
    - High network total alerts
    - Network anomaly alerts
    - CPU mining detection alerts
    - Crypto mining pattern alerts
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    alerts = monitor.get_network_alerts(limit=limit)

    return {"alerts": alerts, "count": len(alerts)}


@app.get("/api/alerts/critical")
async def get_critical_alerts(limit: int = 20):
    """Get critical alerts only (auto-killed containers, severe issues)."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    alerts = monitor.get_critical_alerts(limit=limit)

    return {"alerts": alerts, "count": len(alerts)}


@app.get("/api/containers/{container_id}/alerts")
async def get_container_alerts(container_id: str, limit: int = 20):
    """Get security alerts for a specific container."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    alerts = monitor.get_alerts_by_container(container_id, limit=limit)

    return {"alerts": alerts, "count": len(alerts)}


@app.get("/api/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str, tail: int = 100, separate_streams: bool = False
):
    """
    Get container logs.

    Args:
        container_id: Container ID
        tail: Number of lines to retrieve
        separate_streams: If true, return stdout and stderr separately
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    logs = monitor.get_container_logs(
        container_id, tail=tail, separate_streams=separate_streams
    )

    if logs is None:
        raise HTTPException(
            status_code=404, detail="Container not found or logs unavailable"
        )

    if separate_streams and isinstance(logs, dict):
        # Return separate streams
        return {
            "container_id": container_id,
            "stdout": logs.get("stdout", ""),
            "stderr": logs.get("stderr", ""),
            "combined": logs.get("combined", ""),
            "stdout_lines": len(logs.get("stdout", "").split("\n")),
            "stderr_lines": len(logs.get("stderr", "").split("\n")),
        }
    else:
        # Backward compatible - return combined logs
        return {
            "container_id": container_id,
            "logs": logs,
            "lines": len(logs.split("\n")),
        }


@app.post("/api/containers/{container_id}/kill")
async def kill_container(container_id: str):
    """
    Kill/terminate a container.

    Args:
        container_id: Container ID (short or full)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    try:
        # Get the container
        container = monitor.docker_client.containers.get(container_id)

        # Kill the container
        container.kill()

        logger.info(
            f"🔪 Container {container.name} ({container_id}) killed via dashboard"
        )

        return {
            "success": True,
            "message": f"Container {container.name} killed successfully",
            "container_id": container_id,
        }
    except Exception as e:
        logger.error(f"Failed to kill container {container_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to kill container: {str(e)}"
        )


@app.get("/api/requests/history")
async def get_mcp_request_history(limit: int = 50):
    """
    Get MCP function call history from MCP server.

    Args:
        limit: Number of recent requests to return (default: 50)
    """
    # Use absolute path relative to this server file to avoid CWD issues
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_file = os.path.join(base_dir, "mcp_requests.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                requests = json.load(f)
                # Get last N requests in reverse order (newest first)
                recent = list(reversed(requests[-limit:]))
                return {"requests": recent, "count": len(recent)}
        else:
            return {"requests": [], "count": 0}
    except Exception as e:
        logger.error(f"Error reading MCP request history: {e}")
        return {"requests": [], "count": 0}


@app.get("/api/ml/model_info")
async def get_ml_model_info():
    """Return ML model details (RandomForest) and feature importances if available."""
    try:
        model_info = {
            "model_type": "RandomForestClassifier",
            "features": [
                "cpu_mean",
                "cpu_std",
                "cpu_max",
                "cpu_min",
                "cpu_trend",
                "cpu_sustained_high",
                "cpu_sustained_moderate",
                "mem_mean",
                "mem_std",
                "mem_trend",
                "net_rx_rate_mean",
                "net_tx_rate_mean",
                "net_total_bytes",
                "net_variance",
                "block_read_rate",
                "block_write_rate",
                "execution_duration",
                "sample_count",
                "output_repetition_score",
            ],
            "feature_importance": None,
        }

        # Optional: read last training metrics for importances if available
        base_dir = os.path.dirname(os.path.abspath(__file__))
        metrics_dir = os.path.join(base_dir, "training_artifacts", "metrics")
        latest_metrics = os.path.join(metrics_dir, "latest_training.json")
        if os.path.exists(latest_metrics):
            with open(latest_metrics, "r") as f:
                data = json.load(f)
                # New schema stores importance_scores as a map
                importance_scores = (
                    data.get("features", {}).get("importance_scores")
                    if isinstance(data.get("features"), dict)
                    else None
                )
                if importance_scores and isinstance(importance_scores, dict):
                    # Align scores with the known features list
                    model_info["feature_importance"] = [
                        float(importance_scores.get(name, 0.0))
                        for name in model_info["features"]
                    ]

        return model_info
    except Exception as e:
        logger.error(f"Error loading ML model info: {e}")
        return {
            "model_type": "RandomForestClassifier",
            "features": [],
            "feature_importance": None,
        }


@app.get("/api/llm/reviews")
async def get_llm_reviews(limit: int = 20):
    """Return recent LLM code reviews from file."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        reviews_file = os.path.join(base_dir, "llm_reviews.json")

        if os.path.exists(reviews_file):
            with open(reviews_file, "r") as f:
                reviews = json.load(f)
                recent = list(reversed(reviews[-limit:]))
                return {"reviews": recent, "count": len(recent)}
        else:
            return {"reviews": [], "count": 0}
    except Exception as e:
        logger.error(f"Error reading LLM reviews: {e}")
        return {"reviews": [], "count": 0}


@app.get("/api/ml/classifications")
async def get_ml_classifications(limit: int = 50):
    """Return recent ML classification alerts only (ML mining/suspicious)."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    try:
        alerts = monitor.get_network_alerts(limit=limit)
        # Filter for ML-specific alert types
        ml_alerts = [
            a
            for a in alerts
            if a.get("alert_type") in ("ml_mining_detected", "ml_suspicious_detected")
        ]
        return {"alerts": ml_alerts, "count": len(ml_alerts)}
    except Exception as e:
        logger.error(f"Error reading ML classifications: {e}")
        return {"alerts": [], "count": 0}


@app.get("/api/ml/predictions")
async def get_ml_predictions(limit: int = 100):
    """Return ALL recent ML predictions (not just alerts above threshold)."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    try:
        predictions = monitor.get_ml_predictions(limit=limit)
        return {"predictions": predictions, "count": len(predictions)}
    except Exception as e:
        logger.error(f"Error reading ML predictions: {e}")
        return {"predictions": [], "count": 0}


@app.get("/api/ml/timeseries")
async def get_ml_timeseries(container_id: str = None):
    """Return time series of predictions for wave graph visualization."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    try:
        timeseries = monitor.get_ml_time_series(container_id=container_id)
        return {"timeseries": timeseries, "count": len(timeseries)}
    except Exception as e:
        logger.error(f"Error reading ML time series: {e}")
        return {"timeseries": [], "count": 0}


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """Run the dashboard server."""
    logger.info(f"Starting dashboard server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_dashboard()
