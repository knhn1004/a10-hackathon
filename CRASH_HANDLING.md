# Crash Handling & Error Recovery

## Overview

The Code Sandbox MCP now includes comprehensive crash detection, logging, and recovery mechanisms. When containers crash due to resource limits, code errors, or other issues, the system:

1. **Detects the crash** automatically via monitoring
2. **Collects detailed crash information** (exit codes, logs, metrics)
3. **Notifies the observability dashboard** with crash events
4. **Returns helpful error messages** to the MCP caller with troubleshooting tips

## Features

### 🔍 Automatic Crash Detection

The monitoring system continuously tracks container status and detects crashes:

```python
# Automatically detects:
- Out-of-Memory (OOM) kills
- Segmentation faults
- Signal kills (SIGTERM, SIGKILL)
- Non-zero exit codes
- Container status transitions (running → exited)
```

### 📋 Crash Information Collected

For each crash, the system captures:

| Information | Description |
|------------|-------------|
| **Exit Code** | Container exit code (137=SIGKILL, 139=SEGFAULT, etc.) |
| **OOM Killed** | Whether killed by out-of-memory |
| **Error Message** | Docker error message if available |
| **Container Logs** | Last 100 lines with **separate stdout/stderr streams** |
| **Last Metrics** | CPU, memory, network stats before crash |
| **Crash Reason** | Human-readable crash classification |
| **Timestamp** | When the crash occurred |

### 🗑️ Automatic Container Cleanup

The dashboard automatically removes metrics for deleted containers:

- Monitors which containers exist in Docker
- Removes stale metrics from dashboard on each collection cycle
- Cleans up tracking data for non-existent containers
- Prevents dashboard from showing "ghost" containers

### 🎯 Crash Reasons Detected

| Crash Reason | Exit Code | Description |
|--------------|-----------|-------------|
| `OUT_OF_MEMORY` | 137 + OOM flag | Container exceeded 512MB memory limit |
| `PROCESS_LIMIT_EXCEEDED` | 137 | Too many processes (fork bomb detected) |
| `KILLED_BY_SIGNAL_9` | 137 | Forcefully killed (often OOM) |
| `SEGMENTATION_FAULT` | 139 | Memory access violation |
| `TERMINATED_SIGTERM` | 143 | Gracefully terminated |
| `GENERAL_ERROR` | 1 | Generic error |
| `NON_ZERO_EXIT_X` | X | Exited with code X |

## Usage

### 1. MCP Client (Claude)

When code execution causes a crash, the MCP returns detailed information:

```
User: "Create a sandbox and allocate 1GB of memory"

Claude calls: create_sandbox()
Claude calls: execute_python(code="import numpy as np; arr = np.zeros((1024,1024,128))")

Response:
🔥 CONTAINER CRASHED DURING EXECUTION

Crash Reason: OUT_OF_MEMORY
Exit Code: 137
OOM Killed: True

Code that caused the crash:
------------------------------------------------------------
import numpy as np
arr = np.zeros((1024, 1024, 128))  # ~1GB
------------------------------------------------------------

Container Logs (last 50 lines):
------------------------------------------------------------
Allocating large array...
[timestamp] Killed
------------------------------------------------------------

Troubleshooting:
- If OOM: The code used too much memory (limit: 512MB). Try processing smaller datasets.
- If SIGKILL: The process was forcefully terminated, usually due to resource limits.

Check the observability dashboard for detailed metrics.
```

### 2. Observability Dashboard

The dashboard displays crash information in real-time.

#### View All Crashes

```bash
# Start dashboard
./run_dashboard.sh

# Open browser
open http://localhost:8080
```

Navigate to the dashboard to see:
- **Recent Crashes** section showing last 10 crashes
- **Crash History** with full details
- **Per-Container Crash** information

#### API Endpoints

```bash
# Get all crashes
curl http://localhost:8080/api/crashes?limit=50

# Get crash for specific container
curl http://localhost:8080/api/containers/{container_id}/crash

# Get container logs (combined)
curl http://localhost:8080/api/containers/{container_id}/logs?tail=100

# Get container logs with separate stdout/stderr
curl http://localhost:8080/api/containers/{container_id}/logs?tail=100&separate_streams=true

# Get overview (includes recent crashes)
curl http://localhost:8080/api/overview
```

**New: Separate Stream Example**

```bash
curl "http://localhost:8080/api/containers/abc123/logs?separate_streams=true"
```

Returns:
```json
{
  "container_id": "abc123",
  "stdout": "Normal output\nMore output\n",
  "stderr": "Warning: something\nError: failed\n",
  "combined": "Normal output\nWarning: something\n...",
  "stdout_lines": 2,
  "stderr_lines": 2
}
```

### 3. Python API

```python
from monitor import get_monitor

monitor = get_monitor()

# Get crash history
crashes = monitor.get_crash_history(limit=20)
for crash in crashes:
    print(f"Container {crash['name']} crashed:")
    print(f"  Reason: {crash['crash_reason']}")
    print(f"  Exit Code: {crash['exit_code']}")
    print(f"  OOM: {crash['oom_killed']}")
    
    # Crash logs now have separate streams
    logs = crash['last_logs']
    print(f"  Stdout: {logs['stdout'][:100]}...")
    print(f"  Stderr: {logs['stderr'][:100]}...")

# Get crash for specific container
crash = monitor.get_crash_by_container("sandbox_abc123")
if crash:
    print(f"Last crash: {crash['crash_reason']}")
    print(f"Stdout:\n{crash['last_logs']['stdout']}")
    print(f"Stderr:\n{crash['last_logs']['stderr']}")

# Get container logs (backward compatible - combined)
logs = monitor.get_container_logs("sandbox_abc123", tail=50)
print(logs)

# Get container logs with separate streams
logs = monitor.get_container_logs("sandbox_abc123", tail=50, separate_streams=True)
print(f"Stdout:\n{logs['stdout']}")
print(f"Stderr:\n{logs['stderr']}")
```

## Testing

Run the crash handling test suite:

```bash
# Make sure docker is running
docker ps

# Run crash handling tests
poetry run python test_crash_handling.py

# Run stdout/stderr separation and cleanup tests
poetry run python test_stream_separation.py
```

**test_crash_handling.py** tests:
1. ✅ Normal execution (baseline)
2. ✅ Out-of-memory crash
3. ✅ Segmentation fault
4. ⚠️  Infinite loop (optional, takes 30s)

**test_stream_separation.py** tests:
1. ✅ Stdout/stderr stream separation
2. ✅ Dashboard cleanup of removed containers
3. ✅ Crash logs with separate streams

## Common Crash Scenarios

### Out of Memory (OOM)

**Cause:** Code tries to allocate more than 512MB

**Example:**
```python
import numpy as np
# Allocate 1GB - exceeds limit
arr = np.zeros((1024, 1024, 128), dtype=np.float64)
```

**Solution:**
- Process data in smaller chunks
- Use memory-efficient algorithms
- Request higher memory limit (if available)

### Segmentation Fault

**Cause:** Invalid memory access (usually from C extensions)

**Example:**
```python
import ctypes
# Dereference null pointer
ctypes.string_at(0)
```

**Solution:**
- Check C extension code
- Validate pointers and memory access
- Use pure Python alternatives

### Fork Bomb / Process Limit

**Cause:** Code creates too many processes (limit: 100)

**Example:**
```python
import os
while True:
    os.fork()  # Creates exponentially more processes
```

**Solution:**
- Avoid recursive forking
- Use process pools with fixed size
- Use `subprocess.run()` instead of `os.fork()`
- Consider asyncio for concurrency

See [FORK_BOMB_PROTECTION.md](FORK_BOMB_PROTECTION.md) for details.

### Infinite Loop / Timeout

**Cause:** Code runs too long and hits timeout

**Example:**
```python
while True:
    pass  # Never terminates
```

**Solution:**
- Add exit conditions to loops
- Use timeout-aware algorithms
- Break computation into smaller steps

### Import Errors

**Cause:** Module not available in sandbox

**Example:**
```python
import tensorflow  # Not installed
```

**Solution:**
- Check available packages
- Use `install_package` if supported
- Use alternative packages

## Architecture

### Crash Detection Flow

```
┌─────────────────┐
│  Container      │
│  Running        │
└────────┬────────┘
         │ (code executes)
         ▼
┌─────────────────┐
│  Resource Limit │
│  Exceeded       │
└────────┬────────┘
         │ (OOM/SIGKILL)
         ▼
┌─────────────────┐
│  Container      │
│  Status: exited │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Monitor Detects        │
│  Status Change          │
│  (running → exited)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Collect Crash Info:    │
│  - Exit code            │
│  - Docker inspect       │
│  - Container logs       │
│  - Last metrics         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Store in Crash         │
│  History (deque)        │
└────────┬────────────────┘
         │
         ├──────────────────┐
         ▼                  ▼
┌─────────────────┐  ┌──────────────┐
│  Dashboard API  │  │  MCP Caller  │
│  /api/crashes   │  │  Gets Error  │
└─────────────────┘  └──────────────┘
```

### Crash Information Structure

```python
@dataclass
class ContainerCrash:
    container_id: str          # Short container ID
    name: str                  # Container name
    crash_time: float          # Unix timestamp
    exit_code: int             # Container exit code
    error: str                 # Docker error message
    oom_killed: bool           # OOM killed flag
    last_logs: str             # Last 100 lines of logs
    last_metrics: Dict         # Metrics before crash
    crash_reason: str          # Human-readable reason
```

## Configuration

### Memory Limits

Edit `mcp_server.py`:

```python
# Change container memory limit
container = docker_client.containers.run(
    IMAGE_NAME,
    mem_limit="512m",  # Change to "1g", "2g", etc.
    memswap_limit="512m"
)
```

### Crash History Size

Edit `monitor.py`:

```python
# Keep more crash history
self.crash_history: Deque[ContainerCrash] = deque(maxlen=100)  # Default
# Change to maxlen=500 for more history
```

### Log Tail Size

Edit crash collection in `monitor.py`:

```python
# Get more/fewer log lines
logs = await asyncio.to_thread(
    container.logs,
    tail=100  # Change to 200, 500, etc.
)
```

## Troubleshooting

### Crashes Not Appearing in Dashboard

1. **Check monitoring is enabled:**
   ```bash
   # Look for this in logs
   grep "Container monitoring started" <log_file>
   ```

2. **Verify container has sandbox label:**
   ```bash
   docker ps -a --filter "label=sandbox=1"
   ```

3. **Check monitor is running:**
   ```bash
   # Dashboard server should show
   curl http://localhost:8080/api/health
   ```

### Missing Logs

If crash logs are empty:

```python
# Container might be removed too quickly
# Adjust cleanup timeout in mcp_server.py
IDLE_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "300"))
```

### False Positive Crashes

If normal stops are detected as crashes:

```python
# Adjust crash detection logic in monitor.py
if previous_status == 'running' and current_status in ['exited', 'dead']:
    # Add additional checks here
    if exit_code != 0 or oom_killed:
        # Only report actual crashes
        ...
```

## Future Enhancements

- [ ] **Alert System**: Send webhooks/emails on crash
- [ ] **Crash Analytics**: Pattern detection and statistics
- [ ] **Auto-Recovery**: Automatically restart crashed containers
- [ ] **Core Dumps**: Collect and analyze core dumps
- [ ] **Performance Profiling**: CPU/memory profiles before crash
- [ ] **Crash Clustering**: Group similar crashes
- [ ] **Predictive Detection**: Predict crashes before they occur

## API Reference

### Monitor API

```python
class ContainerMonitor:
    def get_crash_history(limit: int = 20) -> List[Dict]:
        """Get recent crash history."""
        
    def get_crash_by_container(container_id: str) -> Optional[Dict]:
        """Get most recent crash for specific container."""
        
    def get_container_logs(container_id: str, tail: int = 100) -> Optional[str]:
        """Get container logs."""
        
    def get_container_details(container_id: str) -> Optional[Dict]:
        """Get detailed container info including OOM flag."""
```

### Dashboard API

```
GET  /api/crashes?limit=50              - Get crash history
GET  /api/containers/{id}/crash         - Get container's last crash
GET  /api/containers/{id}/logs?tail=100 - Get container logs
GET  /api/overview                      - Includes recent_crashes
```

### MCP Server

```python
class SandboxManager:
    @staticmethod
    async def _handle_container_crash(container, sandbox_id, code) -> Dict:
        """Handle container crash and return detailed error."""
```

## Contributing

To add new crash detection logic:

1. Update `_determine_crash_reason()` in `monitor.py`
2. Add exit code mapping
3. Update documentation
4. Add test case to `test_crash_handling.py`

Example:

```python
def _determine_crash_reason(self, exit_code: int, error: str, oom_killed: bool) -> str:
    if exit_code == 134:  # SIGABRT
        return "ABORTED_ABNORMALLY"
    # ... add more patterns
```

## License

MIT

