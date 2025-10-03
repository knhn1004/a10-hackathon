# Crash Handling Implementation Summary

## ✅ What Was Implemented

Based on your requirements to handle extreme requests that crash the runner, I've implemented a comprehensive crash handling system that:

### 1. ✅ **Notifies the Observability Dashboard About Crashes**

**Implementation:**
- Added crash detection to `monitor.py` that tracks container status transitions
- When a container goes from `running` → `exited/dead`, it's automatically detected as a crash
- Crash events are stored in a rolling history (last 100 crashes)
- Dashboard API exposes crash information via:
  - `/api/crashes` - Get all crash history
  - `/api/containers/{id}/crash` - Get specific container crash
  - `/api/overview` - Includes recent crashes section

**Files Modified:**
- `monitor.py` - Added `ContainerCrash` dataclass, crash detection logic
- `dashboard_server.py` - Added crash endpoints

### 2. ✅ **Shows Logs of Running Code When It Crashed**

**Implementation:**
- Automatically captures last 100 lines of container logs when crash detected
- Logs are stored with crash information and displayed in error messages
- Available via:
  - Dashboard API: `/api/containers/{id}/logs`
  - MCP error response (includes logs inline)
  - Python API: `monitor.get_container_logs()`

**Files Modified:**
- `monitor.py` - Added `get_container_logs()` method
- `dashboard_server.py` - Added logs endpoint
- `mcp_server.py` - Crash handler includes logs in error message

### 3. ✅ **Returns Error Info to MCP Caller**

**Implementation:**
- Enhanced `execute_code()` to detect crashes and return detailed error information
- MCP caller receives:
  - Crash reason (OOM, SIGKILL, SEGFAULT, etc.)
  - Exit code and error message
  - Container logs (last 50 lines)
  - Code snippet that caused crash
  - Troubleshooting tips
  - Link to observability dashboard

**Files Modified:**
- `mcp_server.py` - Added `_handle_container_crash()` method
- Enhanced error handling in `execute_code()`
- Improved error formatting in MCP tool response

## 📋 Features Added

### Crash Detection System

```python
# Automatically detects:
✅ Out-of-Memory (OOM) kills
✅ Segmentation faults (exit 139)
✅ Signal kills (exit 137, 143)
✅ General errors (exit 1)
✅ Any non-zero exit code
```

### Crash Information Collected

For each crash:
- **Exit Code** (137, 139, etc.)
- **OOM Killed** flag
- **Error Message** from Docker
- **Container Logs** (last 100 lines)
- **Last Metrics** (CPU, memory before crash)
- **Crash Reason** (human-readable)
- **Timestamp**

### Dashboard Integration

The observability dashboard now shows:
- Recent crashes section in overview
- Crash history page
- Per-container crash details
- Real-time crash notifications

## 🧪 Testing

Created comprehensive test suite:

```bash
poetry run python test_crash_handling.py
```

Tests:
1. ✅ Normal execution (baseline)
2. ✅ Out-of-memory crash
3. ✅ Segmentation fault
4. ✅ Infinite loop timeout

## 📊 Example: OOM Crash Flow

### Before (Without Crash Handling):
```
User: "Allocate 1GB of memory"
→ Container crashes
→ Connection error
→ Generic "Sandbox not found" error
→ No crash information
→ No logs
```

### After (With Crash Handling):
```
User: "Allocate 1GB of memory"
→ Container crashes
→ Monitor detects crash
→ Collects exit code, logs, metrics
→ Stores in crash history
→ Returns detailed error to MCP:

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
[2024-01-01 12:34:56] Allocating large array...
[2024-01-01 12:34:57] Killed
------------------------------------------------------------

Troubleshooting:
- If OOM: The code used too much memory (limit: 512MB)
  Try processing smaller datasets or use memory-efficient algorithms.

Check the observability dashboard for detailed metrics.
```

## 🎯 Usage Examples

### 1. In Claude Desktop (MCP Client)

```
User: Create a sandbox and run code that uses too much memory

Claude:
1. create_sandbox() → sandbox_id: abc123
2. execute_python(code="import numpy as np; np.zeros((1024,1024,128))")

Response shows:
🔥 CONTAINER CRASHED 🔥
[Full crash details with logs and troubleshooting]
```

### 2. Observability Dashboard

```bash
# Start dashboard
./run_dashboard.sh

# View crashes
open http://localhost:8080

# API access
curl http://localhost:8080/api/crashes
curl http://localhost:8080/api/containers/abc123/crash
curl http://localhost:8080/api/containers/abc123/logs
```

### 3. Python API

```python
from monitor import get_monitor

monitor = get_monitor()

# Get all crashes
crashes = monitor.get_crash_history(limit=20)

# Get specific container crash
crash = monitor.get_crash_by_container("abc123")
print(f"Reason: {crash['crash_reason']}")
print(f"Logs:\n{crash['last_logs']}")

# Get container logs
logs = monitor.get_container_logs("abc123", tail=100)
```

## 📁 Files Modified/Created

### Modified Files (3):
1. **`monitor.py`** - Added crash detection and logging (~150 lines)
   - `ContainerCrash` dataclass
   - `detect_crashes()` method
   - `_collect_crash_info()` method
   - `_determine_crash_reason()` method
   - `get_crash_history()` method
   - `get_crash_by_container()` method
   - `get_container_logs()` method

2. **`mcp_server.py`** - Enhanced error handling (~100 lines)
   - `_handle_container_crash()` method
   - Improved `execute_code()` with crash detection
   - Better error formatting for MCP responses

3. **`dashboard_server.py`** - Added crash endpoints (~40 lines)
   - `/api/crashes` endpoint
   - `/api/containers/{id}/crash` endpoint
   - `/api/containers/{id}/logs` endpoint
   - Added `recent_crashes` to overview

### Created Files (2):
1. **`test_crash_handling.py`** - Test suite for crash scenarios
2. **`CRASH_HANDLING.md`** - Comprehensive documentation

**Total Addition:** ~300 lines of production code + documentation

## 🚀 Quick Start

### 1. Test the Crash Handling

```bash
# Build Docker image
docker build -t code-sandbox:latest .

# Start monitoring dashboard
./run_dashboard.sh

# In another terminal, run crash tests
poetry run python test_crash_handling.py
```

### 2. View Crashes in Dashboard

```bash
open http://localhost:8080
# Navigate to Crashes section
```

### 3. Use with MCP (Claude)

The crash handling works automatically when:
- Container runs out of memory
- Code causes segmentation fault
- Container is killed by signal
- Any abnormal termination occurs

## 🎁 Benefits

### For Users:
✅ Clear error messages with crash reason  
✅ Container logs showing what happened  
✅ Troubleshooting tips for common issues  
✅ Link to dashboard for detailed analysis  

### For Developers:
✅ Crash history API for analytics  
✅ Automatic crash detection  
✅ Structured crash information  
✅ Easy to extend with new crash types  

### For Operations:
✅ Real-time crash monitoring  
✅ Historical crash data  
✅ Resource usage before crash  
✅ Crash pattern analysis  

## 🔮 Future Enhancements

Potential additions:
- [ ] Alert webhooks on crash
- [ ] Crash pattern detection
- [ ] Auto-restart on certain crashes
- [ ] Core dump collection
- [ ] Predictive crash prevention
- [ ] Crash clustering and analytics

## 📝 Summary

You asked for three things, and now you have them all:

1. ✅ **Dashboard Notifications** - Crashes appear in real-time on dashboard
2. ✅ **Crash Logs** - Last 100 lines of logs captured and displayed
3. ✅ **MCP Error Returns** - Detailed crash info returned to caller with troubleshooting

**No more silent failures!** Every crash is detected, logged, and reported with actionable information. 🎉

