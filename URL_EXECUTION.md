# URL-Based Code Execution

## Overview

The `execute_from_url` tool allows you to fetch Python code from a URL and execute it in a sandbox. This is useful for:

- Running code from GitHub gists
- Testing code from pastebin or similar services  
- Executing shared code snippets
- Running remote scripts securely

## Usage

### Basic Usage

**In Claude Desktop:**

```
User: "Create a sandbox and run the code from this gist: 
       https://gist.githubusercontent.com/user/abc123/raw/script.py"

Claude:
1. create_sandbox() → sandbox_id: xyz789
2. execute_from_url(sandbox_id="xyz789", url="https://...")
   
Result:
📥 Fetched code from: https://gist.githubusercontent.com/...
   Size: 256 bytes
   Content-Type: text/plain

📊 Execution Status: success

📝 Output:
Hello from the gist!
Result: 42
```

### MCP Tool API

```python
execute_from_url(
    sandbox_id: str,  # Sandbox to execute in
    url: str          # URL to fetch code from
)
```

**Parameters:**
- `sandbox_id` - ID of an existing sandbox (create one first with `create_sandbox`)
- `url` - Public HTTP/HTTPS URL pointing to Python code

**Returns:**
- Fetched code metadata (size, content-type)
- Execution results (stdout, stderr, plots, errors)
- Crash information (if container crashes)

## Security Features

### ✅ URL Validation

**Allowed:**
- `http://` URLs
- `https://` URLs
- Public domains and IP addresses

**Blocked:**
- `file://` URLs
- `ftp://` URLs  
- `localhost` / `127.0.0.1`
- Private IP ranges:
  - `192.168.*.*`
  - `10.*.*.*`
  - `172.16.*.*`

**Example Blocked URLs:**
```python
# These will be rejected:
"file:///etc/passwd"           # File URLs blocked
"ftp://example.com/code.py"    # FTP not allowed
"http://localhost/code.py"     # Localhost blocked
"http://192.168.1.1/code.py"   # Private IP blocked
```

### 📏 Size Limits

**Maximum code size:** 1MB (1,048,576 bytes)

Files larger than this are rejected to prevent:
- Memory exhaustion
- DoS attacks
- Excessive bandwidth usage

### ⏱️ Timeout Protection

**URL fetch timeout:** 10 seconds

Prevents hanging on:
- Slow servers
- Unresponsive URLs
- Network issues

### 🔍 Content-Type Checking

**Allowed content-types:**
- `text/plain`
- `text/x-python`
- `application/x-python-code`
- `application/octet-stream`

**Note:** Content-type is checked but not strictly enforced (warning only).

### 🔒 Execution Isolation

All fetched code runs in the same secure sandbox as normal code:

- Docker container isolation
- Resource limits (CPU, memory, PIDs)
- Network isolation
- Fork bomb protection
- Automatic cleanup

## Supported Sources

### GitHub Gists

**Raw gist URLs:**
```
https://gist.githubusercontent.com/username/gist_id/raw/filename.py
```

**Example:**
```python
# Get the "Raw" URL from a gist
url = "https://gist.githubusercontent.com/johndoe/abc123def456/raw/example.py"
execute_from_url(sandbox_id, url)
```

### Pastebin

**Raw pastebin URLs:**
```
https://pastebin.com/raw/paste_id
```

**Example:**
```python
url = "https://pastebin.com/raw/xyz789"
execute_from_url(sandbox_id, url)
```

### Direct File URLs

Any publicly accessible HTTP/HTTPS URL:

```python
url = "https://example.com/scripts/mycode.py"
execute_from_url(sandbox_id, url)
```

## Error Handling

### Invalid URL

```
❌ Error fetching code from URL:
Invalid URL scheme: ftp. Allowed: http, https
```

### Blocked URL

```
❌ Error fetching code from URL:
Cannot fetch from localhost URLs
```

### Size Exceeded

```
❌ Error fetching code from URL:
Code size exceeds limit: 2097152 bytes (max: 1048576)
```

### Network Error

```
❌ Error fetching code from URL:
Network error fetching URL: Connection refused
```

### HTTP Error

```
❌ Error fetching code from URL:
Failed to fetch URL: HTTP 404
```

### Timeout

```
❌ Error fetching code from URL:
Timeout fetching URL (>10.0s)
```

### Empty Content

```
❌ Error fetching code from URL:
URL returned empty content
```

## Examples

### Example 1: Simple Script

**URL Content:**
```python
# hello.py
print("Hello from URL!")
for i in range(5):
    print(f"Count: {i}")
```

**Execution:**
```python
sandbox = create_sandbox()
result = execute_from_url(sandbox['sandbox_id'], "https://example.com/hello.py")
```

**Output:**
```
📥 Fetched code from: https://example.com/hello.py
   Size: 89 bytes
   Content-Type: text/plain

📊 Execution Status: success

📝 Output:
Hello from URL!
Count: 0
Count: 1
Count: 2
Count: 3
Count: 4
```

### Example 2: Data Analysis

**URL Content:**
```python
# analyze.py
import numpy as np
import pandas as pd

data = np.array([1, 2, 3, 4, 5])
df = pd.DataFrame({'values': data})

print(f"Mean: {df['values'].mean()}")
print(f"Std:  {df['values'].std()}")
```

**Execution:**
```python
execute_from_url(sandbox_id, "https://gist.github.com/.../analyze.py")
```

**Output:**
```
📥 Fetched code from: https://gist.github.com/.../analyze.py
   Size: 187 bytes

📊 Execution Status: success

📝 Output:
Mean: 3.0
Std:  1.5811388300841898
```

### Example 3: Visualization

**URL Content:**
```python
# plot.py
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 2*np.pi, 100)
y = np.sin(x)

plt.plot(x, y)
plt.title('Sine Wave')
plt.show()
```

**Execution:**
```python
execute_from_url(sandbox_id, "https://example.com/plot.py")
```

**Output:**
```
📥 Fetched code from: https://example.com/plot.py
   Size: 156 bytes

📊 Execution Status: success

🖼️  Generated matplotlib plot (base64 image, 45678 chars)
```

### Example 4: Error Handling

**URL Content:**
```python
# error.py
print("Starting...")
raise ValueError("Something went wrong!")
print("This won't execute")
```

**Execution:**
```python
execute_from_url(sandbox_id, "https://example.com/error.py")
```

**Output:**
```
📥 Fetched code from: https://example.com/error.py
   Size: 112 bytes

📊 Execution Status: error

📝 Output:
Starting...

❌ Error:
Traceback (most recent call last):
  File "<string>", line 3, in <module>
ValueError: Something went wrong!
```

## Configuration

Edit `mcp_server.py` to adjust settings:

```python
# Maximum code size (default: 1MB)
MAX_CODE_SIZE = 1024 * 1024  # bytes

# URL fetch timeout (default: 10 seconds)
URL_FETCH_TIMEOUT = 10.0  # seconds

# Allowed URL schemes
ALLOWED_URL_SCHEMES = ["http", "https"]

# Allowed content types
ALLOWED_CONTENT_TYPES = [
    "text/plain",
    "text/x-python",
    "application/x-python-code",
    "application/octet-stream",
]
```

## Testing

Run the test suite:

```bash
poetry run python test_url_execution.py
```

Tests:
1. ✅ URL validation (scheme, localhost, private IPs)
2. ✅ Security features (size limit, timeout)
3. ✅ Code execution from URL
4. ✅ Error handling

## Best Practices

### 1. Verify Source

**Always verify the URL source before executing:**
```python
# Good: Known trusted source
url = "https://gist.githubusercontent.com/trusted-user/abc/raw/code.py"

# Bad: Unknown or untrusted source
url = "http://sketchy-site.com/code.py"
```

### 2. Use HTTPS

**Prefer HTTPS over HTTP:**
```python
# Good: Encrypted connection
url = "https://example.com/code.py"

# Less secure: Unencrypted
url = "http://example.com/code.py"
```

### 3. Check Code First

**For untrusted sources, fetch and review before executing:**
```python
# Option 1: Use execute_python with the code
code = requests.get(url).text
print(code)  # Review it first
execute_python(sandbox_id, code)

# Option 2: Use execute_from_url (code is logged)
execute_from_url(sandbox_id, url)
```

### 4. Handle Errors

**Always handle potential errors:**
```python
try:
    result = execute_from_url(sandbox_id, url)
    if result.get('status') == 'crashed':
        print("Container crashed!")
    elif result.get('status') == 'error':
        print("Code had errors")
except ValueError as e:
    print(f"Failed to fetch: {e}")
```

### 5. Clean Up

**Delete sandboxes when done:**
```python
sandbox = create_sandbox()
try:
    execute_from_url(sandbox['sandbox_id'], url)
finally:
    delete_sandbox(sandbox['sandbox_id'])
```

## Common Use Cases

### Running GitHub Gists

```
User: "Run this gist: https://gist.github.com/user/abc123"

Claude:
1. Create sandbox
2. Execute code from gist URL
3. Show results
4. Clean up
```

### Testing Code Snippets

```
User: "Test this code from pastebin: https://pastebin.com/raw/xyz"

Claude:
1. Create sandbox
2. Fetch and execute from URL
3. Report any errors
4. Show output
```

### Running Remote Scripts

```
User: "Run the example script from the docs"

Claude:
1. Find documentation URL
2. Create sandbox
3. Execute script from docs
4. Display results
```

## Troubleshooting

### "Cannot fetch from localhost"

**Cause:** Trying to fetch from localhost or 127.0.0.1

**Solution:** Use a public URL instead. If testing locally, deploy to a public server first.

### "Code size exceeds limit"

**Cause:** File is larger than 1MB

**Solution:** 
- Split code into smaller modules
- Remove unnecessary code
- Use data files separately

### "Timeout fetching URL"

**Cause:** Server is slow or unresponsive

**Solution:**
- Check if the URL is accessible
- Try a different URL
- Check your network connection

### "Invalid URL scheme"

**Cause:** Using file://, ftp://, or other non-HTTP(S) protocol

**Solution:** Use http:// or https:// URLs only

## Comparison with execute_python

| Feature | execute_from_url | execute_python |
|---------|------------------|----------------|
| **Code Source** | Remote URL | Direct string |
| **Size Limit** | 1MB | No specific limit |
| **Validation** | URL security checks | None |
| **Network** | Required to fetch | Not required |
| **Use Case** | Shared code, gists | Inline code, testing |

**When to use execute_from_url:**
- Running code from GitHub gists
- Testing shared code snippets
- Executing remote scripts
- Running code from documentation

**When to use execute_python:**
- Testing small code snippets
- Running generated code
- Quick calculations
- Direct code execution

## API Reference

### fetch_code_from_url()

```python
@staticmethod
async def fetch_code_from_url(url: str) -> Dict[str, Any]:
    """
    Fetch code from a URL with security checks.
    
    Args:
        url: URL to fetch code from
        
    Returns:
        {
            "code": str,          # Fetched code content
            "url": str,           # Original URL
            "size": int,          # Size in bytes
            "content_type": str   # Content-Type header
        }
        
    Raises:
        ValueError: If URL is invalid or fetch fails
    """
```

### execute_from_url Tool

```python
Tool(
    name="execute_from_url",
    description="Fetch Python code from a URL and execute it in a sandbox",
    inputSchema={
        "sandbox_id": str,  # Required: Sandbox ID
        "url": str          # Required: URL to fetch from
    }
)
```

## Security Considerations

### ✅ Safe Practices

1. **URL Validation:** All URLs are validated before fetching
2. **Sandbox Isolation:** Code runs in isolated Docker containers
3. **Resource Limits:** Same limits as normal execution (CPU, memory, PIDs)
4. **Timeout Protection:** 10-second fetch timeout
5. **Size Limits:** 1MB maximum code size
6. **Private IP Blocking:** Cannot access internal networks

### ⚠️ Risks to Consider

1. **Malicious Code:** URL could contain malicious code (mitigated by sandbox)
2. **Changed Content:** Code at URL could change between checks (use specific versions/commits)
3. **MITM Attacks:** HTTP (not HTTPS) is vulnerable (prefer HTTPS)
4. **Data Exfiltration:** Code could attempt to send data out (mitigated by network isolation)

### 🛡️ Recommended Practices

1. **Use HTTPS URLs** whenever possible
2. **Trust the source** - only use URLs from trusted sources
3. **Use specific versions** - use commit hashes in GitHub URLs
4. **Review code first** if from untrusted source
5. **Enable network isolation** for sensitive environments

## Summary

✅ **Securely fetch and execute code from URLs**  
✅ **Support for GitHub gists, pastebin, direct URLs**  
✅ **Comprehensive security checks**  
✅ **Size and timeout limits**  
✅ **Full sandbox isolation**  
✅ **Clear error messages**  
✅ **Easy to use**  

The `execute_from_url` tool makes it easy to run shared code while maintaining security through URL validation, size limits, timeouts, and sandbox isolation! 🚀

