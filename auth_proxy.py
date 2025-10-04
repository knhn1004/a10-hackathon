#!/usr/bin/env python3
"""
Authentication proxy for MCP server.
Validates tokens against dashboard, then forwards to mcpo backend.

Usage:
    # Start mcpo WITHOUT --api-key:
    uvx mcpo --port 8001 -- python mcp_server.py

    # Start this proxy:
    python auth_proxy.py

    # Proxy listens on 8000, forwards to mcpo on 8001
"""
import asyncio
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8080")
BACKEND_URL = "http://localhost:8001"  # mcpo backend

app = FastAPI(title="MCP Auth Proxy")


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
    """Validate token and proxy to backend."""
    # Public endpoints (no auth required)
    PUBLIC_PATHS = ["/proxy-health", "/openapi.json", "/docs", "/redoc"]

    if request.url.path in PUBLIC_PATHS:
        # Allow public access - forward directly to backend
        if request.url.path == "/proxy-health":
            return JSONResponse(content={"status": "ok"})

        # Forward OpenAPI/docs requests without auth
        url = f"{BACKEND_URL}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"

        try:
            backend_response = await http_client.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                content=await request.body(),
            )

            # Add no-cache headers for OpenAPI spec
            response_headers = dict(backend_response.headers)
            if request.url.path == "/openapi.json":
                response_headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response_headers["Pragma"] = "no-cache"
                response_headers["Expires"] = "0"

            return Response(
                content=backend_response.content,
                status_code=backend_response.status_code,
                headers=response_headers,
            )
        except Exception as e:
            logger.error(f"Backend error for {request.url.path}: {e}")
            return JSONResponse(
                status_code=502, content={"detail": "Backend unavailable"}
            )

    # Protected endpoints - require auth
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        logger.warning(f"Missing Bearer token for {request.url.path}")
        return JSONResponse(status_code=401, content={"detail": "Missing Bearer token"})

    token = auth.replace("Bearer ", "")

    # Validate
    validation = await validate_token(token)
    if not validation.get("valid"):
        logger.warning(f"Invalid token for {request.url.path}")
        return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    # Log successful auth
    user_id = validation.get("user_id", "unknown")
    logger.info(f"✅ {user_id} → {request.method} {request.url.path}")

    # Forward to backend
    url = f"{BACKEND_URL}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"

    try:
        # Forward request to mcpo
        backend_response = await http_client.request(
            method=request.method,
            url=url,
            headers=dict(request.headers),
            content=await request.body(),
        )

        # Return backend response
        return Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=dict(backend_response.headers),
        )
    except Exception as e:
        logger.error(f"Backend error: {e}")
        return JSONResponse(status_code=502, content={"detail": "Backend unavailable"})


if __name__ == "__main__":
    import uvicorn

    logger.info("🛡️  Starting Auth Proxy")
    logger.info(f"   Dashboard: {DASHBOARD_URL}")
    logger.info(f"   Backend (mcpo): {BACKEND_URL}")
    logger.info(f"   Proxy listening on: http://0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000)
