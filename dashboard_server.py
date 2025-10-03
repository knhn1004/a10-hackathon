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
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from monitor import get_monitor, ContainerMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# Create FastAPI app
app = FastAPI(
    title="Code Sandbox Observability Dashboard",
    description="Real-time monitoring and observability for Docker-based code sandboxes",
    version="1.0.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global monitor instance
monitor: Optional[ContainerMonitor] = None


@app.on_event("startup")
async def startup_event():
    """Start the monitoring service."""
    global monitor
    monitor = get_monitor()
    
    # Start monitoring in background
    asyncio.create_task(monitor.start_monitoring())
    logger.info("Dashboard server started, monitoring active")


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
        "monitoring_active": monitor is not None
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
    
    return {
        "metrics": metrics,
        "count": len(metrics)
    }


@app.get("/api/containers")
async def get_all_containers():
    """Get latest metrics for all containers."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")
    
    metrics = monitor.get_all_container_metrics()
    
    return {
        "containers": metrics,
        "count": len(metrics)
    }


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
        raise HTTPException(status_code=404, detail="Container not found or no metrics available")
    
    return {
        "container_id": container_id,
        "metrics": metrics,
        "count": len(metrics)
    }


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
        raise HTTPException(status_code=404, detail="Container not found or no metrics available")
    
    # Calculate statistics
    cpu_values = [m['cpu_percent'] for m in metrics]
    memory_values = [m['memory_usage_mb'] for m in metrics]
    memory_percent_values = [m['memory_percent'] for m in metrics]
    
    def calc_stats(values):
        if not values:
            return {"min": 0, "max": 0, "avg": 0}
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2)
        }
    
    return {
        "container_id": container_id,
        "sample_count": len(metrics),
        "cpu_percent": calc_stats(cpu_values),
        "memory_usage_mb": calc_stats(memory_values),
        "memory_percent": calc_stats(memory_percent_values),
        "latest": metrics[-1] if metrics else None
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
            cpu_avg = sum(m['cpu_percent'] for m in history) / len(history) if history else 0
            
            container_summaries.append({
                "id": container_id,
                "name": latest['name'],
                "status": latest['status'],
                "cpu_percent": latest['cpu_percent'],
                "cpu_avg_1m": round(cpu_avg, 2),
                "memory_usage_mb": latest['memory_usage_mb'],
                "memory_percent": latest['memory_percent'],
                "uptime": latest['timestamp'] - latest['created_at'],
                "image": latest['image']
            })
    
    # Sort by CPU usage
    container_summaries.sort(key=lambda x: x['cpu_percent'], reverse=True)
    
    return {
        "system": latest_system,
        "containers": container_summaries,
        "summary": {
            "total_containers": len(all_containers),
            "running_containers": sum(1 for c in container_summaries if c['status'] == 'running'),
            "total_cpu_percent": sum(c['cpu_percent'] for c in container_summaries),
            "total_memory_mb": sum(c['memory_usage_mb'] for c in container_summaries)
        }
    }


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """Run the dashboard server."""
    logger.info(f"Starting dashboard server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_dashboard()

