# Mining Detection Error Clarity - Fix Summary

## Problem

When the monitoring system detected and terminated a container for mining activity, the user received an **unclear error message**:

```
❌ Execution failed:
Server disconnected without sending a response.
```

This was **not helpful** because it didn't explain:
- ✗ Why the container was terminated
- ✗ That mining was detected
- ✗ What the security implications were
- ✗ How to avoid this in the future

## Root Causes

### 1. Missing Exception Handler

The code didn't catch `httpx.RemoteProtocolError`, which is what happens when the server disconnects mid-request:

```python
# OLD CODE - Missing RemoteProtocolError
except httpx.ConnectError:
    # Only caught ConnectError, not RemoteProtocolError
```

### 2. Generic Crash Messages

Even when crashes were detected, the message didn't distinguish between:
- Mining detection (security feature)
- Out of memory (resource limit)
- Fork bombs (process limit)
- Other crashes (bugs in code)

## Solution

### 1. Added RemoteProtocolError Handling

```python
# NEW CODE - Catches both connection errors
except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
    logger.warning(f"Connection error during execution: {type(e).__name__}: {e}")
    await asyncio.to_thread(container.reload)
    if container.status != "running":
        return await SandboxManager._handle_container_crash(
            container, sandbox_id, code
        )
    raise ValueError(f"Cannot connect to sandbox - connection error: {type(e).__name__}")
```

### 2. Enhanced Mining Detection in Crash Handler

```python
# Check if it was mining detection
if "mining" in crash_info.get('crash_reason', '').lower():
    crash_reason = "🔪 TERMINATED BY MINING DETECTOR"
    mining_detected = True
```

### 3. Created Specific Error Messages

#### For Mining Detection:

```
⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED

🔪 The monitoring system detected cryptocurrency mining activity and terminated the container.

🔍 Monitor Detection:
  Reason: Container terminated for suspected mining activity
  Exit Code: 137
  OOM Killed: False

Exit Code: 137

⚠️  Mining Activity Indicators:
- Sustained high CPU usage (near 50% quota limit)
- Continuous hashing operations detected
- Pattern matching: mining/cryptocurrency keywords
- ML model flagged the activity as suspicious

Code that triggered the detection:
------------------------------------------------------------
[code snippet shown]
------------------------------------------------------------

📊 This is a security feature that protects against:
- Cryptocurrency mining abuse
- Resource exhaustion attacks  
- Unauthorized compute usage

Check the observability dashboard for detailed metrics and detection logs.
```

#### For Regular Crashes:

```
🔥 CONTAINER CRASHED DURING EXECUTION

Crash Reason: OUT_OF_MEMORY
Exit Code: 137
OOM Killed: True

[crash details and troubleshooting]
```

## What Changed

### Modified Files

**`mcp_server.py`** - Three key changes:

1. **Lines 425-433**: Added `httpx.RemoteProtocolError` to exception handling
   ```python
   except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
   ```

2. **Lines 494-525**: Enhanced crash reason detection
   ```python
   if "mining" in crash_info.get('crash_reason', '').lower():
       crash_reason = "🔪 TERMINATED BY MINING DETECTOR"
       mining_detected = True
   ```

3. **Lines 527-588**: Separate error messages for mining vs regular crashes
   ```python
   if mining_detected:
       error_message = f"""⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED..."""
   else:
       error_message = f"""🔥 CONTAINER CRASHED DURING EXECUTION..."""
   ```

4. **Lines 594-604**: Added `mining_detected` flag to crash info
   ```python
   "crash_info": {
       "mining_detected": mining_detected,
       ...
   }
   ```

### Created Files

- **`test_mining_detection_error.py`** - Test suite for error messages
- **`MINING_ERROR_CLARITY_FIX.md`** - This document

## Testing

### Test Results

```bash
$ poetry run python test_mining_detection_error.py

Testing Mining Detection Error Messages
✅ Mining detection header
✅ Mentions monitoring system
✅ Shows indicators
✅ Explains it's a security feature
✅ Sets mining_detected flag

Testing Regular Crash Error Messages
✅ Regular crash header
✅ Shows OOM reason
✅ mining_detected flag is False
✅ No mining emoji

✅ ALL TESTS PASSED!
```

## Before vs After

### Before (Unclear)

```
❌ Execution failed:
Server disconnected without sending a response.
```

User thinks: "What? Why? Is this a bug?"

### After (Clear)

```
⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED

🔪 The monitoring system detected cryptocurrency mining activity 
   and terminated the container.

⚠️  Mining Activity Indicators:
- Sustained high CPU usage (near 50% quota limit)
- Continuous hashing operations detected
- Pattern matching: mining/cryptocurrency keywords
- ML model flagged the activity as suspicious

📊 This is a security feature that protects against:
- Cryptocurrency mining abuse
- Resource exhaustion attacks  
- Unauthorized compute usage
```

User thinks: "Oh! The security system caught this. That's good to know!"

## Benefits

### For Users

✅ **Clear explanation** - Understand exactly what happened  
✅ **Security awareness** - Know the system is protecting them  
✅ **Educational** - Learn what triggers detection  
✅ **Actionable** - See code that caused the issue  

### For Operators

✅ **Better debugging** - Clear distinction between crash types  
✅ **Security visibility** - Mining attempts are obvious  
✅ **Audit trail** - Full details logged  
✅ **Monitoring integration** - Leverages existing monitoring data  

### For Security

✅ **Deterrence** - Clear message discourages abuse  
✅ **Transparency** - Users understand security features  
✅ **Compliance** - Clear documentation of security actions  
✅ **Detection feedback** - Users see what patterns trigger alerts  

## Exception Types Handled

| Exception | Cause | Handling |
|-----------|-------|----------|
| `httpx.TimeoutException` | Request timeout | Check if crashed, else timeout error |
| `httpx.ConnectError` | Can't connect to container | Check if crashed, else connection error |
| `httpx.RemoteProtocolError` | Server disconnected | **NEW**: Check if crashed, else protocol error |

## Crash Reasons Detected

| Exit Code | OOM | Pattern | Crash Reason | Message Type |
|-----------|-----|---------|--------------|--------------|
| 137 | No | Mining in logs | 🔪 TERMINATED BY MINING DETECTOR | Mining-specific |
| 137 | Yes | - | OUT_OF_MEMORY | Regular crash |
| 137 | No | Fork/process | PROCESS_LIMIT_EXCEEDED | Regular crash |
| 137 | No | Other | KILLED (SIGKILL) | Regular crash |
| 139 | - | - | SEGMENTATION_FAULT | Regular crash |

## Example: Your Mining.py Case

### What Happened

1. User: `execute_from_url(sandbox_id, "https://.../mining.py")`
2. MCP: Fetched 4,228 bytes ✅
3. MCP: Started executing in sandbox
4. Monitor: Detected sustained 50% CPU + hashing patterns
5. Monitor: **Terminated container** (Exit 137)
6. Container: HTTP server died mid-request
7. MCP: Caught `RemoteProtocolError`
8. MCP: Detected container crashed
9. MCP: Found mining in crash reason
10. User: Received clear mining detection message ✅

### Old Response (Unclear)

```
📥 Fetched code from: https://.../mining.py
   Size: 4228 bytes

❌ Execution failed:
Server disconnected without sending a response.
```

### New Response (Clear)

```
📥 Fetched code from: https://.../mining.py
   Size: 4228 bytes

⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED

🔪 The monitoring system detected cryptocurrency mining activity 
   and terminated the container.

🔍 Monitor Detection:
  Reason: Container terminated for suspected mining activity
  Exit Code: 137
  OOM Killed: False

⚠️  Mining Activity Indicators:
- Sustained high CPU usage (near 50% quota limit)
- Continuous hashing operations detected
- Pattern matching: mining/cryptocurrency keywords
- ML model flagged the activity as suspicious

[Full code and logs shown]

📊 This is a security feature that protects against:
- Cryptocurrency mining abuse
- Resource exhaustion attacks  
- Unauthorized compute usage
```

## Summary

✅ **Fixed** - `RemoteProtocolError` now caught and handled  
✅ **Enhanced** - Mining detection creates specific error message  
✅ **Tested** - All error message scenarios verified  
✅ **Clear** - Users get informative, actionable messages  

The error messages are now **crystal clear** when mining is detected! 🎉

## Related Features

This fix enhances the existing security stack:
- ✅ Mining detection (ML + pattern matching)
- ✅ Resource limits (CPU, memory, PIDs)
- ✅ Fork bomb protection
- ✅ Network isolation
- ✅ **NEW: Clear error reporting for all the above**

Users now get proper feedback when security features activate!

