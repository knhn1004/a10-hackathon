# URL Execution Tool - Implementation Summary

## ✅ What Was Implemented

A new MCP tool called `execute_from_url` that fetches Python code from a URL and executes it in a sandbox.

## 🎯 Feature Overview

### The Tool

**Name:** `execute_from_url`

**Purpose:** Fetch code from public URLs (GitHub gists, pastebin, etc.) and execute securely in a sandbox

**Parameters:**
- `sandbox_id` (required) - ID of existing sandbox
- `url` (required) - HTTP/HTTPS URL to fetch code from

### Example Usage in Claude

```
User: "Run this gist: https://gist.githubusercontent.com/user/abc/raw/code.py"

Claude:
1. create_sandbox() → sandbox_id: xyz789
2. execute_from_url(
     sandbox_id="xyz789",
     url="https://gist.githubusercontent.com/.../code.py"
   )

Result:
📥 Fetched code from: https://gist.githubusercontent.com/...
   Size: 256 bytes
   Content-Type: text/plain

📊 Execution Status: success

📝 Output:
Hello from the gist!
Result: 42
```

## 🛡️ Security Features

### 1. URL Validation

**Allowed:**
- ✅ `http://` URLs
- ✅ `https://` URLs
- ✅ Public domain names and IPs

**Blocked:**
- ❌ `file://` URLs
- ❌ `ftp://` and other protocols
- ❌ `localhost` / `127.0.0.1`
- ❌ Private IPs (`192.168.*`, `10.*`, `172.16.*`)

### 2. Size Limits

- **Maximum:** 1MB (1,048,576 bytes)
- **Purpose:** Prevent memory exhaustion and DoS attacks

### 3. Timeout Protection

- **Timeout:** 10 seconds
- **Purpose:** Prevent hanging on slow/unresponsive servers

### 4. Content-Type Checking

**Accepted types:**
- `text/plain`
- `text/x-python`
- `application/x-python-code`
- `application/octet-stream`

(Warning only, not strictly enforced)

### 5. Sandbox Isolation

All fetched code runs in the same secure sandbox:
- Docker container isolation
- Resource limits (CPU, memory, PIDs)
- Fork bomb protection
- Network isolation
- Automatic cleanup

## 📁 Files Modified/Created

### Modified (1 file):

**`mcp_server.py`** (~150 lines added)
- Added `fetch_code_from_url()` method with security checks
- Added `execute_from_url` tool definition
- Added tool handler in `call_tool()`
- Added URL validation and fetching logic
- Added configuration constants

### Created (2 files):

1. **`test_url_execution.py`** (~200 lines)
   - Test URL validation
   - Test security features
   - Test code execution from URLs
   - Test error handling

2. **`URL_EXECUTION.md`** (comprehensive documentation)
   - Usage guide
   - Security features
   - Supported sources
   - Error handling
   - Examples
   - Best practices
   - API reference

### Documentation Updated (1 file):

**`README.md`**
- Updated tool count (6 → 7)
- Added `execute_from_url` to tools list
- Added URL execution section
- Added link to documentation

## 🧪 Test Results

```bash
$ poetry run python test_url_execution.py

✅ All URL execution tests completed!

Summary:
  ✅ URL validation working
  ✅ Security checks active
  ✅ Size limits enforced
  ✅ Code execution from URLs supported
```

**Tests:**
1. ✅ URL scheme validation (blocks file://, ftp://)
2. ✅ Localhost blocking (blocks 127.0.0.1, localhost)
3. ✅ Private IP blocking (blocks 192.168.*, 10.*, 172.16.*)
4. ✅ Size limit enforcement (1MB max)
5. ✅ Timeout protection (10 seconds)
6. ✅ Code execution from URLs
7. ✅ Error handling

## 📊 Use Cases

### 1. GitHub Gists

```
User: "Run this gist"
https://gist.githubusercontent.com/user/id/raw/script.py

Claude: Fetches and executes the gist code
```

### 2. Pastebin

```
User: "Execute this pastebin"
https://pastebin.com/raw/xyz789

Claude: Fetches and runs the pasted code
```

### 3. Direct URLs

```
User: "Run the example from docs"
https://example.com/scripts/demo.py

Claude: Downloads and executes the script
```

### 4. Code Sharing

```
User: "Test this shared code"
[provides URL]

Claude: Validates, fetches, and executes securely
```

## 🔒 Security Implementation

### URL Validation Flow

```
1. Parse URL
   └─> Validate scheme (http/https only)
       └─> Check hostname
           ├─> Block localhost
           ├─> Block 127.0.0.1
           └─> Block private IPs
               └─> APPROVED ✓
```

### Fetch Flow

```
1. Create HTTP client with timeout
2. GET request to URL (follow redirects)
3. Check HTTP status (must be 200)
4. Check content-type (warning if unexpected)
5. Check size (<= 1MB)
6. Validate content not empty
7. Return code + metadata
```

### Execution Flow

```
1. Fetch code from URL (validated)
2. Log fetch operation
3. Execute in sandbox (same as execute_python)
4. Return results with URL metadata
```

## 🎁 Benefits

### For Users

✅ **Easy sharing:** Just paste a gist URL  
✅ **No copy/paste:** Code fetched automatically  
✅ **Secure execution:** All sandbox protections apply  
✅ **Clear feedback:** Shows URL, size, content-type  
✅ **Error handling:** Clear messages for failures  

### For Developers

✅ **Code reuse:** Share code via URLs  
✅ **Testing:** Easily test shared snippets  
✅ **Documentation:** Run examples from docs  
✅ **Collaboration:** Share analysis scripts  
✅ **Version control:** Use GitHub URLs  

### For Security

✅ **URL validation:** Prevents SSRF attacks  
✅ **Size limits:** Prevents resource exhaustion  
✅ **Timeouts:** Prevents hanging  
✅ **Sandbox isolation:** Malicious code contained  
✅ **Audit trail:** All fetches logged  

## 📝 Configuration

Edit `mcp_server.py` to customize:

```python
# Maximum code size
MAX_CODE_SIZE = 1024 * 1024  # 1MB

# Fetch timeout
URL_FETCH_TIMEOUT = 10.0  # 10 seconds

# Allowed schemes
ALLOWED_URL_SCHEMES = ["http", "https"]

# Allowed content types
ALLOWED_CONTENT_TYPES = [
    "text/plain",
    "text/x-python",
    "application/x-python-code",
    "application/octet-stream",
]
```

## 🚀 How to Use

### In Claude Desktop

**1. Simple execution:**
```
User: "Create a sandbox and run code from this gist: [URL]"

Claude will:
- Create sandbox
- Fetch code from URL
- Execute and show results
```

**2. With error handling:**
```
User: "Try to run this code: [URL]"

If fetch fails:
❌ Error fetching code from URL:
Invalid URL scheme: ftp. Allowed: http, https

If execution fails:
Shows crash/error details
```

**3. Multiple URLs:**
```
User: "Run these three scripts: [URL1] [URL2] [URL3]"

Claude will:
- Create sandbox
- Execute each URL in sequence
- Show results for each
```

## 🔍 Error Messages

### URL Validation Errors

```
❌ Invalid URL scheme: ftp. Allowed: http, https
❌ Cannot fetch from localhost URLs
❌ Cannot fetch from private IP addresses
```

### Fetch Errors

```
❌ Failed to fetch URL: HTTP 404
❌ Timeout fetching URL (>10.0s)
❌ Network error fetching URL: Connection refused
❌ Code size exceeds limit: 2097152 bytes (max: 1048576)
❌ URL returned empty content
```

### Execution Errors

```
🔥 CONTAINER CRASHED 🔥
(Shows crash details)

❌ Error:
(Shows Python traceback)
```

## 📋 Comparison

| Feature | execute_from_url | execute_python |
|---------|------------------|----------------|
| Code Source | Remote URL | Direct string |
| Size Limit | 1MB max | No specific limit |
| Security | URL validation | None |
| Network | Required | Not required |
| Metadata | URL, size, type | None |
| Use Case | Shared code | Inline code |

## 🎓 Best Practices

### 1. Use HTTPS
```python
# Good
"https://example.com/code.py"

# Less secure
"http://example.com/code.py"
```

### 2. Verify Source
```python
# Good - trusted source
"https://gist.githubusercontent.com/trusted-user/..."

# Risky - unknown source
"http://random-site.com/code.py"
```

### 3. Use Specific Versions
```python
# Good - specific commit
"https://gist.githubusercontent.com/user/id/raw/abc123def456/code.py"

# Risky - can change
"https://gist.githubusercontent.com/user/id/raw/code.py"
```

### 4. Handle Errors
```python
try:
    result = execute_from_url(sandbox_id, url)
except ValueError as e:
    print(f"Failed: {e}")
```

### 5. Clean Up
```python
sandbox = create_sandbox()
try:
    execute_from_url(sandbox['sandbox_id'], url)
finally:
    delete_sandbox(sandbox['sandbox_id'])
```

## 📚 Documentation

Full documentation available in:
- [URL_EXECUTION.md](URL_EXECUTION.md) - Complete guide
- [README.md](README.md) - Quick overview
- Test examples in `test_url_execution.py`

## ✅ Summary

**New feature:** `execute_from_url` tool

**Security:**
✅ URL validation (scheme, localhost, private IPs)  
✅ Size limit (1MB)  
✅ Timeout (10s)  
✅ Full sandbox isolation  
✅ Audit logging  

**Use cases:**
✅ GitHub gists  
✅ Pastebin  
✅ Direct URLs  
✅ Code sharing  
✅ Documentation examples  

**Testing:**
✅ Comprehensive test suite  
✅ All security checks verified  
✅ Error handling tested  

Your MCP can now safely execute code from URLs! 🚀

