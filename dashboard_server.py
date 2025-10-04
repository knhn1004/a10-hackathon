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

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx

from monitor import get_monitor, ContainerMonitor

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

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    import json
    import os

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


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """Run the dashboard server."""
    logger.info(f"Starting dashboard server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_dashboard()
