# Quick Start: Observability

## TL;DR

```bash
# Start the dashboard
./run_dashboard.sh

# Open in browser
http://localhost:8080
```

## What You Get

✅ **Real-time monitoring** of all sandbox containers  
✅ **Beautiful web dashboard** with charts and metrics  
✅ **Docker inspect** integration  
✅ **REST API** for programmatic access  
✅ **MCP tools** for Claude integration

## Quick Demo

### 1. Start the Dashboard

```bash
./run_dashboard.sh
```

You'll see:

```
🚀 Starting Code Sandbox Observability Dashboard
✅ Starting dashboard server on http://localhost:8080

📊 Dashboard features:
   • Real-time container metrics
   • CPU and memory usage graphs
   • Docker inspect integration
   • Resource utilization tracking
```

### 2. Open Dashboard

Open **http://localhost:8080** in your browser.

You'll see:

- System overview (containers, CPU, memory)
- Real-time charts (CPU and memory over time)
- Container cards with live metrics
- Click any container for detailed inspection

### 3. Create Some Sandboxes

In another terminal:

```bash
poetry run python mcp_server.py
```

Or use Claude Desktop with the MCP integration.

### 4. Watch Metrics Update

The dashboard updates every 2 seconds automatically:

- New containers appear instantly
- Charts show resource trends
- Progress bars animate smoothly

## Common Tasks

### View Container Details

**Click any container card** → Opens inspection modal with:

- Basic info (ID, image, status, PID)
- Resource limits
- Performance statistics
- Network configuration
- Full Docker inspect JSON

### Check Resource Usage

Look at the **header cards**:

- Total Containers: How many sandboxes exist
- Total CPU: Aggregate CPU usage
- Total Memory: Combined memory consumption
- System Status: Overall health

### Track Performance Trends

Watch the **charts**:

- CPU chart: Shows CPU usage over last 60 seconds
- Memory chart: Shows memory usage over last 60 seconds
- Hover for exact values

### Find a Specific Container

Containers are sorted by CPU usage (highest first).  
Look for the container name (e.g., `sandbox_abc123`).

## MCP Integration

The MCP server automatically enables monitoring tools.

### In Claude Desktop:

**Inspect a container:**

```
You: "Inspect the sandbox abc123"

Claude calls: inspect_container(sandbox_id="abc123")

Result:
🔍 Container Inspection: sandbox_abc123

📋 Basic Info:
  • ID: abc123
  • Image: code-sandbox:latest
  • Status: running
  • PID: 12345
  ...
```

**Get metrics:**

```
You: "Show me the resource usage for sandbox abc123"

Claude calls: get_container_metrics(sandbox_id="abc123")

Result:
📊 Container Metrics: sandbox_abc123

💻 CPU:
  • Current: 12.5%

💾 Memory:
  • Usage: 45.2 MB
  • Limit: 512.0 MB
  • Percent: 8.8%
  ...
```

## REST API

### Get Overview

```bash
curl http://localhost:8080/api/overview | jq
```

Returns:

```json
{
  "system": {
    "total_containers": 3,
    "running_containers": 3,
    "total_cpu_percent": 25.4,
    "total_memory_mb": 234.5
  },
  "containers": [...],
  "summary": {...}
}
```

### Get Container Metrics

```bash
curl http://localhost:8080/api/containers/abc123 | jq
```

Returns:

```json
{
  "container_id": "abc123",
  "metrics": [
    {
      "cpu_percent": 12.5,
      "memory_usage_mb": 45.2,
      "memory_percent": 8.8,
      ...
    }
  ]
}
```

### Docker Inspect

```bash
curl http://localhost:8080/api/containers/abc123/inspect | jq
```

Returns full Docker inspect JSON.

## Testing

### Run the Test Suite

```bash
poetry run python test_observability.py
```

This will:

1. Create a test container
2. Collect metrics from it
3. Test Docker inspect
4. Verify dashboard API
5. Clean up automatically

Expected output:

```
🧪 Testing Observability System

✅ Docker is running
✅ Monitor initialized
✅ Sandbox image found
🐳 Creating test container...
✅ Test container created: abc123def456

📊 Collecting metrics...
✅ Metrics collected successfully!
📈 Container Metrics:
   CPU: 2.3%
   Memory: 23.1 MB / 512.0 MB (4.5%)
   ...

✨ All monitoring tests passed!
```

## Configuration

### Change Dashboard Port

Edit `dashboard_server.py`:

```python
def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
```

### Change Update Interval

Edit `dashboard.html`:

```javascript
setInterval(updateDashboard, 2000); // milliseconds
```

### Change Metrics History

Edit `monitor.py`:

```python
METRICS_HISTORY_SIZE = 300  # number of samples
COLLECTION_INTERVAL = 1.0   # seconds
```

## Troubleshooting

### Dashboard won't start

**Problem**: Port 8080 in use  
**Solution**:

```bash
# Find what's using the port
lsof -i :8080

# Kill it or change the dashboard port
```

**Problem**: Docker not running  
**Solution**:

```bash
# Start Docker Desktop
# Then check:
docker info
```

### No containers shown

**Problem**: No sandbox containers exist  
**Solution**: Create some sandboxes:

```bash
# Via MCP server
poetry run python mcp_server.py

# Or use Claude Desktop
```

**Problem**: Containers exist but not showing  
**Solution**: Ensure they have the `sandbox=1` label:

```bash
# Check containers
docker ps --filter "label=sandbox=1"
```

### Dashboard shows errors

**Problem**: "Monitor not initialized"  
**Solution**:

```bash
# Restart the dashboard
./run_dashboard.sh
```

**Problem**: "Failed to fetch data"  
**Solution**: Check browser console for errors  
Make sure dashboard server is running on port 8080

### High resource usage

**Problem**: Dashboard using too much CPU  
**Solution**:

```javascript
// Increase update interval in dashboard.html
setInterval(updateDashboard, 5000); // 5 seconds instead of 2
```

**Problem**: Monitoring using too much memory  
**Solution**:

```python
# Reduce history in monitor.py
METRICS_HISTORY_SIZE = 60  # 1 minute instead of 5
```

## Architecture

```
Dashboard (Browser)
      ↓ HTTP
Dashboard Server (:8080)
      ↓
Monitor Module
      ↓ Docker API
Docker Engine
      ↓
Sandbox Containers
```

## File Reference

- **`monitor.py`** - Collects Docker stats and inspect data
- **`dashboard_server.py`** - FastAPI server with REST endpoints
- **`dashboard.html`** - Web UI with charts
- **`run_dashboard.sh`** - Launcher script
- **`test_observability.py`** - Test suite

## Documentation

- **[OBSERVABILITY.md](OBSERVABILITY.md)** - Complete guide
- **[DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)** - Visual walkthrough
- **[OBSERVABILITY_SUMMARY.md](OBSERVABILITY_SUMMARY.md)** - Implementation details

## Tips

1. **Keep dashboard open** while developing
2. **Watch aggregate metrics** to avoid overloading
3. **Click containers** to see detailed inspect data
4. **Use charts** to spot performance trends
5. **Check uptime** to find stuck containers

## Next Steps

1. ✅ Start the dashboard: `./run_dashboard.sh`
2. ✅ Create some sandboxes via MCP server
3. ✅ Watch metrics update in real-time
4. ✅ Click containers to inspect them
5. ✅ Use the REST API for automation

---

**Need help?** See [OBSERVABILITY.md](OBSERVABILITY.md) for detailed documentation.
