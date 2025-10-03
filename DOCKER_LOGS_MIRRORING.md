# Docker Logs Mirroring

## Overview

All Python code executed in sandboxes has its output mirrored to Docker container logs. This provides:
- Real-time monitoring capability via `docker logs`
- Independent debug channel (separate from API responses)
- Audit trail of all code execution
- Container-level observability

## How It Works

The `sandbox_server.py` uses a **Tee I/O** approach:
1. Captures stdout/stderr for API response
2. Simultaneously writes to Docker's stdout
3. Adds clear prefixes and markers for easy parsing

### Implementation

```python
class TeeIO:
    """Tee output to both capture buffer and original stream."""
    
    def write(self, message):
        # Write to capture buffer (for API response)
        self.capture_buffer.write(message)
        
        # Also write to Docker stdout (for logs)
        if message:
            self.original_stream.write(f"{self.prefix}{message}")
            self.original_stream.flush()
```

## Log Format

### Prefixes

- `[STDOUT]` - Standard output from executed code
- `[STDERR]` - Error output from executed code
- `[CODE EXECUTION START]` - Execution begins
- `[CODE EXECUTION COMPLETE]` - Execution succeeds
- `[CODE EXECUTION ERROR]` - Execution fails
- `[IMAGE]` - Matplotlib plot generated

### Example Output

**Successful Execution:**
```
============================================================
[CODE EXECUTION START]
============================================================
[STDOUT] Processing data...
[STDOUT] Mean: 42.5
[STDOUT] Std dev: 12.3
[IMAGE] Generated matplotlib plot (15234 bytes)
============================================================
[CODE EXECUTION COMPLETE]
============================================================
```

**Failed Execution:**
```
============================================================
[CODE EXECUTION START]
============================================================
[STDOUT] Starting calculation...
[STDERR] Warning: deprecated function
============================================================
[CODE EXECUTION ERROR]
============================================================
Traceback (most recent call last):
  File "/app/sandbox_server.py", line 132, in execute_code
    exec(request.code, namespace)
  File "<string>", line 5, in <module>
ValueError: invalid value
============================================================
```

## Usage

### View Logs in Real-Time

```bash
# Follow logs as they're written
docker logs -f <container_id>

# Filter for execution events
docker logs <container_id> | grep "CODE EXECUTION"

# Show only stdout
docker logs <container_id> | grep "\[STDOUT\]"

# Show only errors
docker logs <container_id> | grep "\[STDERR\]\|\[ERROR\]"
```

### View Historical Logs

```bash
# Last 50 lines
docker logs --tail 50 <container_id>

# With timestamps
docker logs -t <container_id>

# Since specific time
docker logs --since 2025-10-03T12:00:00 <container_id>
```

### Programmatic Access

Using Python Docker SDK:
```python
import docker

client = docker.from_env()
container = client.containers.get(container_id)

# Get all logs
logs = container.logs(stdout=True, stderr=True)

# Get separate streams
stdout = container.logs(stdout=True, stderr=False)
stderr = container.logs(stdout=False, stderr=True)

# Stream logs in real-time
for line in container.logs(stream=True, follow=True):
    print(line.decode('utf-8'), end='')
```

## Benefits

### 1. Real-Time Debugging
Monitor code execution as it happens:
```bash
docker logs -f sandbox_abc123
```

### 2. Independent of API
Even if the API request times out or fails, logs are preserved in Docker:
```bash
# Container crashed? Check the logs
docker logs sandbox_abc123 --tail 100
```

### 3. Audit Trail
All code execution is logged with timestamps:
```bash
docker logs -t sandbox_abc123 > audit_trail.log
```

### 4. Integration with Log Aggregators
Works with standard Docker logging drivers:
- `journald` - System journal
- `syslog` - Syslog daemon
- `json-file` - JSON formatted files
- `fluentd` - Fluentd logging
- `awslogs` - AWS CloudWatch
- `splunk` - Splunk logging

### 5. Observability Dashboard Integration
The dashboard automatically displays logs from Docker:
```python
# In dashboard_server.py
logs = monitor.get_container_logs(container_id, separate_streams=True)
# Returns: {"stdout": "...", "stderr": "..."}
```

## Testing

Run the test suite to verify log mirroring:
```bash
poetry run python test_docker_logs.py
```

Expected output:
```
✅ Code stdout mirrored to Docker logs
✅ Code stderr mirrored to Docker logs
✅ Errors logged to Docker logs
✅ Execution markers added for clarity
```

## Configuration

### Disable Log Mirroring (Not Recommended)

If you need to disable mirroring for some reason:

```python
# In sandbox_server.py, change:
stdout_tee = TeeIO(stdout_buffer, old_stdout, prefix="[STDOUT] ")

# To:
stdout_tee = TeeIO(stdout_buffer, io.StringIO(), prefix="")  # Discard to dummy stream
```

### Customize Prefixes

```python
# In sandbox_server.py
stdout_tee = TeeIO(stdout_buffer, old_stdout, prefix="")  # No prefix
stderr_tee = TeeIO(stderr_buffer, old_stderr, prefix="[ERR] ")  # Custom prefix
```

### Adjust Log Verbosity

```python
# In sandbox_server.py, remove execution markers:
# Comment out or remove:
old_stdout.write(f"\n{'='*60}\n")
old_stdout.write("[CODE EXECUTION START]\n")
old_stdout.write(f"{'='*60}\n")
```

## Performance Considerations

### Minimal Overhead
- Writing to stdout is a low-cost operation
- Flushing ensures immediate visibility but adds ~1-2ms per write
- For high-frequency output, consider buffering

### Log Size Management
Docker handles log rotation automatically with the `json-file` driver:
```bash
# Configure in Docker daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Memory Usage
- Logs are stored on disk, not in container memory
- Default max: 30MB (3 files × 10MB)
- Old logs automatically rotated

## Troubleshooting

### Logs Not Appearing

**Problem:** Code executes but logs are empty.

**Check:**
1. Verify the container is using the updated image:
   ```bash
   docker build -t code-sandbox .
   ```

2. Check if stdout is being buffered:
   ```bash
   # Force unbuffered output
   docker exec <container_id> python -u /app/sandbox_server.py
   ```

### Logs Mixed or Garbled

**Problem:** Output appears in wrong order.

**Solution:** The `TeeIO` class calls `flush()` after each write to ensure order. If still an issue, add more aggressive flushing:

```python
def write(self, message):
    self.capture_buffer.write(message)
    self.capture_buffer.flush()  # Add this
    
    if message:
        self.original_stream.write(f"{self.prefix}{message}")
        self.original_stream.flush()
```

### Container Logs Too Large

**Problem:** Logs consuming too much disk space.

**Solution:** Configure Docker log rotation:
```bash
# In docker-compose.yml or docker run
logging:
  driver: "json-file"
  options:
    max-size: "5m"
    max-file: "2"
```

## Best Practices

1. **Always include execution markers** - They make logs easier to parse and debug
2. **Use prefixes** - `[STDOUT]` and `[STDERR]` help distinguish stream types
3. **Flush aggressively** - Ensures real-time visibility in logs
4. **Configure log rotation** - Prevent disk space issues
5. **Integrate with monitoring** - Use log aggregators for production

## Related Features

- **Crash Handling**: Crashes are logged with full tracebacks (see `CRASH_HANDLING.md`)
- **Stream Separation**: stdout/stderr kept separate in monitor (see `monitor.py`)
- **Dashboard Integration**: Logs displayed in real-time on dashboard
- **Fork Bomb Protection**: PID limit violations logged (see `FORK_BOMB_PROTECTION.md`)

## Summary

Docker logs mirroring provides:
- ✅ Real-time monitoring via `docker logs`
- ✅ Independent debug channel
- ✅ Audit trail
- ✅ Container-level observability
- ✅ Integration with standard Docker tools
- ✅ Minimal performance overhead

All with clear prefixes and markers for easy parsing and analysis.

