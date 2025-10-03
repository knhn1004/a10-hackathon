# Fork Bomb Protection

## Problem

Fork bombs are malicious code that create processes exponentially, attempting to:
1. Exhaust system resources
2. Crash the container
3. Make the system unresponsive
4. Potentially affect the host system

**Example fork bomb:**
```python
import os
while True:
    os.fork()  # Creates exponentially more processes
```

## Solution Implemented

### PID Limit

Each sandbox container is now created with a **PID limit of 100 processes**:

```python
container = docker_client.containers.run(
    IMAGE_NAME,
    mem_limit="512m",
    memswap_limit="512m",  # Disable swap
    cpu_period=100000,
    cpu_quota=50000,
    pids_limit=100,  # ⭐ Limit processes to prevent fork bombs
    network_mode="bridge",
    security_opt=["no-new-privileges"],
)
```

### How It Works

1. **Container starts** with PID limit of 100
2. **User code runs** and tries to fork processes
3. **When limit is reached**, Docker kills the container
4. **Container exits** with code 137 (SIGKILL)
5. **Monitor detects** the crash and classifies it as `PROCESS_LIMIT_EXCEEDED`
6. **MCP returns** detailed error with troubleshooting

### Crash Detection

The crash handler now detects fork bombs:

```python
if exit_code == 137:
    # Check if it was PID limit
    if "fork" in logs_str.lower() or "process" in logs_str.lower():
        crash_reason = "PROCESS_LIMIT_EXCEEDED (possible fork bomb)"
    else:
        crash_reason = "KILLED (possibly OOM)"
```

## Error Message

When a fork bomb is detected, users get a clear error:

```
🔥 CONTAINER CRASHED DURING EXECUTION

Crash Reason: PROCESS_LIMIT_EXCEEDED (possible fork bomb)
Exit Code: 137
OOM Killed: False

Code that caused the crash:
------------------------------------------------------------
import os
while True:
    os.fork()
------------------------------------------------------------

Container Logs (last 50 lines):
------------------------------------------------------------
STDOUT:
Created 10 processes...
Created 20 processes...
Created 30 processes...

STDERR:
WARNING: This will create many processes
------------------------------------------------------------

Troubleshooting:
- If PROCESS_LIMIT: Too many processes created (limit: 100). 
  Avoid fork bombs and excessive subprocess creation.
- If SIGKILL: The process was forcefully terminated, usually 
  due to resource limits.

Check the observability dashboard for detailed metrics.
```

## Testing

Test fork bomb protection:

```bash
poetry run python test_fork_bomb.py
```

This test:
1. ✅ Creates a sandbox
2. ✅ Executes fork bomb code
3. ✅ Verifies container is killed
4. ✅ Checks crash reason is `PROCESS_LIMIT_EXCEEDED`
5. ✅ Verifies normal subprocess usage still works

## Resource Limits Summary

| Resource | Limit | Purpose |
|----------|-------|---------|
| **Memory** | 512MB | Prevent OOM crashes |
| **Swap** | Disabled | No swap usage |
| **CPU** | 50% of 1 core | Fair CPU sharing |
| **PIDs** | 100 processes | **Prevent fork bombs** |
| **Network** | Bridge (isolated) | Network security |

## Why 100 Processes?

The limit of **100 processes** is chosen to:

✅ **Allow normal use cases:**
- Python with standard imports (~10-20 processes)
- Subprocess creation for legitimate tasks
- Multiprocessing for parallel computation

❌ **Block malicious use:**
- Fork bombs (exponential growth)
- Process exhaustion attacks
- Resource abuse

**Example normal usage:**
```python
import subprocess
# This works fine (uses ~5 processes)
for i in range(10):
    subprocess.run(['echo', f'Task {i}'])
```

**Example blocked usage:**
```python
import os
# This will hit PID limit and crash
while True:
    os.fork()  # Blocked after 100 processes
```

## Configuration

To adjust the PID limit, edit `mcp_server.py`:

```python
# For stricter limits (more security)
pids_limit=50

# For looser limits (more flexibility)
pids_limit=200

# To disable (not recommended)
# Remove the pids_limit parameter
```

## Monitoring

The observability dashboard now shows:
- PID limit in container details
- Crash reason when PID limit hit
- Process count before crash (in metrics)

**View PID limit:**
```bash
curl http://localhost:8080/api/containers/{id}/inspect
```

Returns:
```json
{
  "pids_limit": 100,
  "exit_code": 137,
  "error": ""
}
```

## Security Benefits

### Before Fork Bomb Protection:

❌ Fork bombs could crash the container  
❌ uvicorn server crashes with "no running event loop"  
❌ Difficult to diagnose the issue  
❌ Potential impact on host system  
❌ Poor user experience  

### After Fork Bomb Protection:

✅ Fork bombs are caught immediately  
✅ Container killed cleanly  
✅ Clear error message with reason  
✅ Host system protected  
✅ Users know what went wrong and how to fix it  

## Related Protections

This complements other security measures:

1. **Memory Limit (512MB)** - Prevents memory exhaustion
2. **CPU Quota (50%)** - Prevents CPU starvation
3. **PID Limit (100)** - **Prevents process exhaustion**
4. **Network Isolation** - Prevents network abuse
5. **No-new-privileges** - Prevents privilege escalation

## Common Scenarios

### Legitimate High Process Usage

If you need more than 100 processes for legitimate reasons:

```python
# Request a sandbox with higher limit
# (future feature - not yet implemented)
create_sandbox(config={"pids_limit": 200})
```

Currently, all sandboxes have a fixed limit of 100 processes.

### Accidental Fork Bombs

Common mistakes that trigger PID limits:

**Bad:**
```python
import os
# Accidentally creates infinite forks
def recursive_fork():
    os.fork()
    recursive_fork()

recursive_fork()  # Fork bomb!
```

**Good:**
```python
import subprocess
# Use subprocess for controlled process creation
subprocess.run(['python', 'script.py'])
```

### Multiprocessing

Multiprocessing is allowed within limits:

```python
from multiprocessing import Pool

# This works (creates ~8 processes)
with Pool(8) as pool:
    results = pool.map(lambda x: x**2, range(100))
```

## Dashboard Integration

Fork bomb crashes show in the dashboard with:
- Exit code: 137
- Reason: `PROCESS_LIMIT_EXCEEDED`
- Logs showing process creation attempts
- Timestamp of when limit was hit

## Future Enhancements

Potential improvements:

- [ ] **Dynamic PID limits** - Adjust based on user tier
- [ ] **Process count monitoring** - Track process creation rate
- [ ] **Pre-emptive detection** - Warn before hitting limit
- [ ] **Process tree visualization** - Show process hierarchy
- [ ] **Configurable limits per sandbox** - Custom limits

## Troubleshooting

### Still Getting Fork Bomb Crashes?

1. **Check PID limit is set:**
   ```bash
   docker inspect sandbox_xyz | grep -i pids
   ```

2. **Verify limit in code:**
   ```bash
   grep pids_limit mcp_server.py
   ```

3. **Check Docker version:**
   ```bash
   docker --version
   # PID limits require Docker 1.13+
   ```

4. **Rebuild containers:**
   ```bash
   docker rm -f $(docker ps -a -q --filter label=sandbox=1)
   docker build -t code-sandbox:latest .
   ```

### Normal Code Hitting Limit?

If legitimate code hits the 100-process limit:

1. **Review process creation** - Are you creating too many subprocesses?
2. **Use process pools** - Reuse processes instead of creating new ones
3. **Async instead of processes** - Consider asyncio for I/O-bound tasks
4. **Request limit increase** - Contact admin (if multi-tenant system)

## Summary

✅ **PID limit of 100** prevents fork bombs  
✅ **Clear error messages** when limit hit  
✅ **Normal usage unaffected** by the limit  
✅ **Dashboard integration** shows PID info  
✅ **Test suite** verifies protection works  

Fork bombs are now properly contained and reported! 🛡️

