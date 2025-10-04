# Auto-Cleanup Feature & Updated MCP Specifications

## 🎯 Problem Solved

**Issue:** Containers remained running after code execution, causing the ML model to continuously analyze idle containers and generate unnecessary predictions.

**Solution:** Added `auto_cleanup` parameter to execution tools and updated MCP tool descriptions to clarify sandbox lifecycle.

---

## ✅ Changes Made

### 1. Updated Tool Descriptions

#### **create_sandbox**
```
IMPORTANT: Sandboxes persist after code execution and must be explicitly deleted.
They will auto-delete after 5 minutes of inactivity.
Use delete_sandbox when done to free resources immediately.
```

#### **execute_python**
```
IMPORTANT: The sandbox remains running after execution completes.
Set auto_cleanup=true to automatically delete the sandbox after execution,
or use delete_sandbox manually when done to stop monitoring.
```

#### **execute_from_url**
```
IMPORTANT: The sandbox remains running after execution completes.
Set auto_cleanup=true to automatically delete the sandbox after execution.
```

---

### 2. Added `auto_cleanup` Parameter

Both `execute_python` and `execute_from_url` now accept:

```json
{
  "auto_cleanup": {
    "type": "boolean",
    "description": "If true, automatically delete the sandbox after execution completes. Default: false",
    "default": false
  }
}
```

---

### 3. Implementation

**File:** `mcp_server.py`

#### execute_python Handler (lines 974-997):
```python
elif name == "execute_python":
    sandbox_id = arguments.get("sandbox_id")
    code = arguments.get("code")
    auto_cleanup = arguments.get("auto_cleanup", False)
    
    result = await SandboxManager.execute_code(
        sandbox_id, code, current_session_id
    )
    
    # Auto-cleanup if requested
    cleanup_message = ""
    if auto_cleanup and result.get("status") != "crashed":
        try:
            await SandboxManager.delete_sandbox(sandbox_id, current_session_id)
            cleanup_message = "\n\n🗑️  Sandbox automatically deleted after execution."
            logger.info(f"Auto-cleaned up sandbox: {sandbox_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-cleanup sandbox {sandbox_id}: {e}")
            cleanup_message = f"\n\n⚠️  Warning: Failed to auto-cleanup sandbox: {e}"
```

#### execute_from_url Handler (lines 1160-1169):
```python
# Auto-cleanup if requested
cleanup_message = ""
if auto_cleanup and result.get("status") != "crashed":
    try:
        await SandboxManager.delete_sandbox(sandbox_id, current_session_id)
        cleanup_message = "\n\n🗑️  Sandbox automatically deleted after execution."
        logger.info(f"Auto-cleaned up sandbox: {sandbox_id}")
    except Exception as e:
        logger.warning(f"Failed to auto-cleanup sandbox {sandbox_id}: {e}")
        cleanup_message = f"\n\n⚠️  Warning: Failed to auto-cleanup sandbox: {e}"
```

---

## 📊 Behavior

### **Default (auto_cleanup=false):**
```
1. Create sandbox
2. Execute code
3. Sandbox remains running
4. ML model continues monitoring
5. Manual cleanup needed (delete_sandbox)
6. Auto-delete after 5 minutes idle
```

### **With auto_cleanup=true:**
```
1. Create sandbox
2. Execute code
3. Sandbox automatically deleted
4. ML model stops monitoring
5. No idle containers
```

---

## 🧪 Usage Examples

### Claude Client Usage

#### **Default - Persistent Sandbox:**
```
User: "Create a sandbox and execute: print('hello')"

Claude will call:
- create_sandbox() → sandbox_abc123
- execute_python(sandbox_id="sandbox_abc123", code="print('hello')")

Result: Container keeps running
```

#### **With Auto-Cleanup:**
```
User: "Create a sandbox, execute this code, and clean up after"

Claude should call:
- create_sandbox() → sandbox_abc123
- execute_python(
    sandbox_id="sandbox_abc123", 
    code="print('hello')",
    auto_cleanup=true
  )

Result: Container automatically deleted
Response includes: "🗑️  Sandbox automatically deleted after execution."
```

---

## 🎯 Benefits

### **For Users:**
- ✅ Clear understanding of sandbox lifecycle
- ✅ Control over resource cleanup
- ✅ Explicit parameter to auto-delete
- ✅ No surprise idle containers

### **For Monitoring:**
- ✅ ML model only analyzes active containers
- ✅ No continuous predictions on idle containers
- ✅ More accurate anomaly detection
- ✅ Cleaner logs and dashboard

### **For Resources:**
- ✅ Faster container cleanup
- ✅ Reduced Docker resource usage
- ✅ Less monitoring overhead
- ✅ Cleaner system state

---

## 🔍 What Happens Now

### **Before This Update:**
```
$ Claude: execute code
✅ Code runs
Container: Still running...
ML Model: suspicious (69%) at 8s
ML Model: suspicious (68%) at 16s
ML Model: suspicious (67%) at 24s
... (continues for 5 minutes)
```

### **After This Update (with auto_cleanup=true):**
```
$ Claude: execute code with auto_cleanup=true
✅ Code runs
🗑️  Sandbox automatically deleted
Container: Deleted
ML Model: (no more predictions)
Dashboard: Shows only the one prediction during execution
```

---

## 📝 Migration Notes

### **No Breaking Changes:**
- `auto_cleanup` defaults to `false`
- Existing behavior unchanged
- Claude must explicitly set `auto_cleanup=true`

### **Recommended Usage:**
- **One-off scripts**: Use `auto_cleanup=true`
- **Interactive sessions**: Use default (false)
- **Multiple executions**: Keep sandbox, delete manually when done

---

## 🚀 Testing

### Test Auto-Cleanup:
```bash
# Via Claude Desktop:
Say: "Create a sandbox, execute print('test'), and use auto_cleanup=true"

# Expected:
- Container created
- Code executes
- Message: "🗑️  Sandbox automatically deleted after execution."
- Container no longer in docker ps
- Dashboard ML tab shows ONE prediction only
```

### Test Default Behavior:
```bash
# Via Claude Desktop:
Say: "Create a sandbox and execute print('test')"

# Expected:
- Container created
- Code executes
- NO cleanup message
- Container still in docker ps
- ML model continues monitoring (multiple predictions)
```

---

## 📊 Dashboard Impact

### **Before:**
```
ML Model Tab:
- sandbox_abc (suspicious 69%) at 8s
- sandbox_abc (suspicious 68%) at 16s
- sandbox_abc (suspicious 67%) at 24s
- sandbox_abc (suspicious 66%) at 32s
... (many predictions)
```

### **After (with auto_cleanup=true):**
```
ML Model Tab:
- sandbox_abc (suspicious 69%) at 8s
(container deleted, no more predictions)
```

---

## 🎉 Summary

| Feature | Before | After |
|---------|--------|-------|
| **Tool Descriptions** | No lifecycle info | Clear lifecycle documentation |
| **Container Cleanup** | Manual only | Manual OR auto |
| **ML Predictions** | Continuous on idle | Only during execution |
| **Dashboard Noise** | Many idle predictions | Clean, relevant data |
| **User Control** | Implicit behavior | Explicit parameter |

**Result:** Users now have full control over sandbox lifecycle with clear documentation! 🎯

