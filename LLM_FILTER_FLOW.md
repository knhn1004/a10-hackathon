# LLM Code Filter Flow

## ✅ All Code Execution Goes Through Ollama LLM Filter

Both `execute_python` and `execute_from_url` use the **same** LLM security filter before executing any code.

---

## 🔄 Flow Diagram

### Method 1: `execute_python`
```
┌─────────────────────────────────────────────────────┐
│ MCP Client: execute_python                         │
│   • sandbox_id: abc123                             │
│   • code: "print('hello')"                         │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ call_tool() handler                                 │
│   Line 747: elif name == "execute_python"          │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ SandboxManager.execute_code()                       │
│   Line 276-350                                      │
│                                                     │
│   ┌─────────────────────────────────────────────┐ │
│   │ 🛡️  LLM SECURITY REVIEW (Line 287-348)    │ │
│   │                                             │ │
│   │ 1. Check if CODE_FILTER_ENABLED            │ │
│   │ 2. Get Ollama LLM filter                   │ │
│   │ 3. Call code_filter.review_code(code)      │ │
│   │    • Timeout: 30 seconds                   │ │
│   │    • Uses: llama3.1:latest                 │ │
│   │                                             │ │
│   │ 4. Check decision:                         │ │
│   │    ✅ APPROVE → Continue to execution       │ │
│   │    ❌ REJECT  → Raise ValueError            │ │
│   └─────────────────────────────────────────────┘ │
│                                                     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼ (if approved)
┌─────────────────────────────────────────────────────┐
│ Execute code in Docker container                    │
└─────────────────────────────────────────────────────┘
```

### Method 2: `execute_from_url`
```
┌─────────────────────────────────────────────────────┐
│ MCP Client: execute_from_url                        │
│   • sandbox_id: abc123                             │
│   • url: https://example.com/mining.py             │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ call_tool() handler                                 │
│   Line 829: elif name == "execute_from_url"        │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ SandboxManager.fetch_code_from_url()                │
│   Line 134-215                                      │
│   • Validates URL                                   │
│   • Fetches code from URL                          │
│   • Returns: code string                           │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ SandboxManager.execute_code()                       │
│   Line 276-350 (SAME AS EXECUTE_PYTHON!)           │
│                                                     │
│   ┌─────────────────────────────────────────────┐ │
│   │ 🛡️  LLM SECURITY REVIEW (Line 287-348)    │ │
│   │                                             │ │
│   │ 1. Check if CODE_FILTER_ENABLED            │ │
│   │ 2. Get Ollama LLM filter                   │ │
│   │ 3. Call code_filter.review_code(code)      │ │
│   │    • Timeout: 30 seconds                   │ │
│   │    • Uses: llama3.1:latest                 │ │
│   │                                             │ │
│   │ 4. Check decision:                         │ │
│   │    ✅ APPROVE → Continue to execution       │ │
│   │    ❌ REJECT  → Raise ValueError            │ │
│   └─────────────────────────────────────────────┘ │
│                                                     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼ (if approved)
┌─────────────────────────────────────────────────────┐
│ Execute code in Docker container                    │
└─────────────────────────────────────────────────────┘
```

---

## 🔑 Key Points

1. **Both tools share the same security path**: `execute_code()` method (lines 276-350)

2. **LLM filter runs BEFORE execution**: 
   - Line 287: Check if `CODE_FILTER_ENABLED`
   - Line 297-300: Call Ollama with 30s timeout
   - Line 311-339: Reject if malicious, else continue

3. **Same protection for both methods**:
   ```python
   execute_python(code) → execute_code(code) → LLM filter → Docker
   execute_from_url(url) → fetch_code() → execute_code(code) → LLM filter → Docker
   ```

4. **Startup confirmation**:
   ```
   🛡️  LLM Code Filter: Enabled
   → All code execution (execute_python & execute_from_url) will be
     analyzed by Ollama LLM before running in sandboxes
   → Malicious code will be rejected automatically
   ```

---

## 🧪 Test It

### Test 1: Direct code execution
```json
{
  "tool": "execute_python",
  "arguments": {
    "sandbox_id": "abc123",
    "code": "import hashlib\nwhile True: hashlib.sha256(b'mining').hexdigest()"
  }
}
```

**Expected**: LLM will reject (crypto mining detected)

### Test 2: URL-based execution
```json
{
  "tool": "execute_from_url",
  "arguments": {
    "sandbox_id": "abc123",
    "url": "https://example.com/mining.py"
  }
}
```

**Expected**: LLM will reject (same crypto mining code)

---

## 📊 Logs to Watch

When LLM filter is active, you'll see:

```
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:   Container: abc123
INFO:code-sandbox-mcp:   Code length: 156 bytes
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: REJECT
INFO:code-sandbox-mcp:   Confidence: 95.0%
INFO:code-sandbox-mcp:   Threats: crypto_mining, infinite_loop
INFO:code-sandbox-mcp:   Reasons: Uses hashlib for mining; Infinite while loop
ERROR:code-sandbox-mcp:❌ CODE REJECTED by LLM filter for sandbox abc123
```

---

## 🚨 Common Issues

### Issue: "Server disconnected without sending a response"
**Cause**: Container is already dead (stopped/killed)

**Solution**: Create a NEW sandbox first
```json
{
  "tool": "create_sandbox"
}
```

Then use the NEW sandbox_id in your execute calls.

### Issue: LLM filter timeout
**Behavior**: After 30s, execution proceeds WITHOUT LLM review

**Logs**:
```
ERROR:code-sandbox-mcp:⏱️ LLM filter timed out after 30 seconds
WARNING:code-sandbox-mcp:⚠️ Proceeding with code execution WITHOUT LLM review
```

**Note**: The container monitoring will still catch malicious activity!

---

## ✨ Summary

- ✅ **Both** `execute_python` and `execute_from_url` use Ollama LLM
- ✅ Malicious code is **rejected before execution**
- ✅ 30-second timeout prevents hanging
- ✅ Graceful fallback if LLM fails
- ✅ Container monitoring as second layer of defense

