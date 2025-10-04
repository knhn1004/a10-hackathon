# 📊 MCP Request History Dashboard

## Overview

The dashboard now includes a **new tab** to view all MCP (Model Context Protocol) requests in real-time. This allows you to monitor:
- Code execution requests
- Sandbox creation/deletion
- URL-based code execution
- Request status (success/error/crashed)
- Timestamps and arguments

## 🎯 Features

### 1. **Tabbed Interface**
The dashboard now has two tabs:
- **Active Containers** - View running containers and metrics (original view)
- **MCP Requests** - View request history from the MCP server

### 2. **Request History Tracking**
The MCP server automatically logs:
- ✅ Tool name (execute_python, create_sandbox, etc.)
- ✅ Timestamp
- ✅ Arguments (sandbox ID, code length, URLs)
- ✅ Status (success, error, crashed)
- ✅ Result preview (first 200 characters)
- ✅ Session ID

### 3. **Real-time Updates**
- Auto-refreshes every 2 seconds when viewing MCP Requests tab
- Shows last 20 requests by default
- Color-coded status badges

### 4. **Clean UI**
- **Success** - Green badge for successful executions
- **Error** - Red badge for errors
- **Crashed** - Orange badge for container crashes
- Monospace preview of results

## 🚀 Usage

### View MCP Requests

1. **Start the dashboard**:
```bash
python dashboard_server.py
```

2. **Open browser**:
```
http://localhost:8080
```

3. **Click "MCP Requests" tab** at the top

### What You'll See

Each request shows:
```
┌─────────────────────────────────────────────┐
│ execute_python                    SUCCESS   │
│ 10:23:45 • sandbox: abc123 • code: 247 bytes│
│ 📊 Execution Status: success                │
│ 📝 Output:                                  │
│ Hello, world!                                │
└─────────────────────────────────────────────┘
```

## 📡 API Endpoint

### Get Request History

```http
GET /api/mcp/requests?limit=50
```

**Response:**
```json
{
  "requests": [
    {
      "timestamp": 1696348800.123,
      "tool": "execute_python",
      "arguments": {
        "sandbox_id": "abc123",
        "code_length": 247
      },
      "status": "success",
      "result_preview": "📊 Execution Status: success\n\n📝 Output:\nHello, world!",
      "session_id": "session_xyz"
    }
  ],
  "count": 1
}
```

## 🔍 Request Types

### execute_python
```javascript
{
  tool: "execute_python",
  arguments: {
    sandbox_id: "abc123",
    code_length: 247
  },
  status: "success"
}
```

### create_sandbox
```javascript
{
  tool: "create_sandbox",
  arguments: {},
  status: "success"
}
```

### execute_from_url
```javascript
{
  tool: "execute_from_url",
  arguments: {
    sandbox_id: "abc123",
    url: "https://example.com/code.py"
  },
  status: "success"
}
```

### delete_sandbox
```javascript
{
  tool: "delete_sandbox",
  arguments: {
    sandbox_id: "abc123"
  },
  status: "success"
}
```

## 🎨 Status Badges

| Status | Badge | Description |
|--------|-------|-------------|
| success | 🟢 GREEN | Code executed successfully |
| error | 🔴 RED | Error in request or execution |
| crashed | 🟠 ORANGE | Container crashed during execution |

## 🔧 Configuration

### Change History Size

In `mcp_server.py`:
```python
MAX_HISTORY_SIZE = 100  # Keep last 100 requests
```

### Change Display Limit

In dashboard, modify the fetch call:
```javascript
await fetch('/api/mcp/requests?limit=50')  // Show last 50
```

## 📊 Use Cases

### 1. **Debugging**
See exactly what code was executed and when it failed

### 2. **Monitoring**
Track how many executions are happening

### 3. **Audit Trail**
Keep record of all MCP interactions

### 4. **Performance Analysis**
Identify patterns in crashes or errors

### 5. **Security**
Monitor for suspicious execution patterns

## 🔄 Data Flow

```
MCP Client
    ↓
MCP Server (logs request)
    ↓
Request History (in-memory)
    ↓
Dashboard API (/api/mcp/requests)
    ↓
Dashboard UI (MCP Requests tab)
```

## 💡 Tips

### Filter by Status

In future updates, you could add filtering:
```javascript
// Show only errors
requests.filter(r => r.status === 'error')

// Show only recent
requests.filter(r => Date.now() - r.timestamp * 1000 < 60000)
```

### Export History

Save request history to file:
```bash
curl http://localhost:8080/api/mcp/requests?limit=100 > requests.json
```

### Clear History

Restart the MCP server (history is in-memory):
```bash
# Restart clears history
python mcp_server.py
```

## 🎯 Example Workflow

### Scenario: Debug Failed Execution

1. **User reports error** in code execution

2. **Open dashboard** → Click "MCP Requests" tab

3. **Find the failed request** (red ERROR badge)

4. **View details**:
   - Timestamp: When it happened
   - Sandbox ID: Which container
   - Code length: How much code
   - Result preview: Error message

5. **Check container logs** for more details

6. **Fix and retry**

## 🚀 Future Enhancements

Potential additions:
- [ ] Click request to expand full details
- [ ] Filter by status/tool/sandbox
- [ ] Search functionality
- [ ] Export to CSV/JSON
- [ ] Request replay (re-execute code)
- [ ] Link request to container in Active Containers tab
- [ ] Show execution time
- [ ] Group by session
- [ ] Syntax highlighting for code previews

## 🔐 Security Notes

- Request history is **in-memory only** (cleared on restart)
- Limited to last 100 requests to prevent memory issues
- No sensitive data (passwords, keys) should be in request history
- Consider sanitizing result previews if needed

## 📝 Technical Details

### Storage

Requests stored in Python list:
```python
request_history: list = []  # Global in mcp_server.py
```

### Logging Function

```python
def log_request(tool_name, arguments, result, status):
    request_entry = {
        "timestamp": time.time(),
        "tool": tool_name,
        "arguments": arguments,
        "status": status,
        "result_preview": result[:200],  # First 200 chars
        "session_id": current_session_id,
    }
    request_history.append(request_entry)
```

### Retrieval

```python
def get_request_history(limit=50):
    return list(reversed(request_history[-limit:]))
```

## 🎉 Summary

The MCP Request History feature provides:
- ✅ **Visibility** into all MCP operations
- ✅ **Real-time monitoring** with auto-refresh
- ✅ **Clean interface** with tabs
- ✅ **Status indicators** for quick scanning
- ✅ **Debugging support** with detailed previews
- ✅ **Minimal overhead** (in-memory, bounded size)

Perfect for monitoring, debugging, and auditing your code execution sandbox! 🚀

