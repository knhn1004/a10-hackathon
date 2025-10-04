# Per-User MCP Architecture

## Overview

The auth proxy has been transformed into a **Per-User MCP Process Manager**. Each authenticated user gets their own isolated `mcpo` instance with their API token passed as environment variables.

## Architecture

```
┌─────────┐    Bearer Token    ┌──────────────────┐
│  User 1 ├────────────────────►                  │
└─────────┘                     │                  │      ┌─────────────────┐
                                │   Auth Proxy     ├──────► mcpo (port 9000)│
┌─────────┐    Bearer Token    │   (port 8000)    │      │  USER_ID=user1  │
│  User 2 ├────────────────────►                  │      │  MCP_API_TOKEN= │
└─────────┘                     │                  │      │    user1_token  │
                                │  - Validates     │      └────────┬────────┘
┌─────────┐    Bearer Token    │  - Spawns mcpo   │               │
│  User 3 ├────────────────────►  - Routes        │      ┌────────▼────────┐
└─────────┘                     │                  │      │  mcp_server.py  │
                                └──────────────────┘      └─────────────────┘
                                         │
                                         │
                                    ┌────▼──────────────┐
                                    │ mcpo (port 9001)  │
                                    │  USER_ID=user2    │
                                    │  MCP_API_TOKEN=   │
                                    │    user2_token    │
                                    └────────┬──────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  mcp_server.py  │
                                    └─────────────────┘
```

## Key Features

### 1. **Dynamic Process Spawning**
- When a user makes their first authenticated request, the proxy spawns a dedicated `mcpo` instance
- Each `mcpo` runs on a unique port (starting from 9000)
- The user's Bearer token is passed as `MCP_API_TOKEN` environment variable

### 2. **Session Management**
- Maintains a mapping: `user_id -> McpoInstance`
- Each instance tracks:
  - User ID
  - Port number
  - Process handle
  - Creation time
  - Last accessed time

### 3. **Request Routing**
- All authenticated requests are routed to the user's specific `mcpo` instance
- The proxy transparently forwards requests and responses

### 4. **Automatic Cleanup**
- Background task runs every 60 seconds
- Idle sessions (no activity for 1 hour) are terminated
- Ports are released back to the pool

### 5. **Process Health Checking**
- Detects when `mcpo` processes die
- Automatically respawns on next request

## Usage

### Start the Proxy

```bash
# Simple start
python auth_proxy.py

# Or with poetry
poetry run python auth_proxy.py
```

### Client Connection

Clients connect as before with their Bearer token:

```bash
# Claude Desktop config example
{
  "mcpServers": {
    "my-mcp": {
      "url": "http://localhost:8000",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

### Admin Endpoints

**Health Check:**
```bash
curl http://localhost:8000/proxy-health
# Returns: {"status": "ok", "active_sessions": 2}
```

**List Active Sessions:**
```bash
curl http://localhost:8000/admin/sessions
# Returns session details for all active users
```

## Environment Variables

The proxy accepts:

- `DASHBOARD_URL` - Dashboard URL for token validation (default: `http://localhost:8080`)

Each spawned `mcpo` receives:

- `MCP_API_TOKEN` - The user's Bearer token
- `USER_ID` - The user's ID from validation
- `DASHBOARD_URL` - Forwarded from proxy

## Configuration

Edit `auth_proxy.py` to adjust:

```python
BASE_PORT = 9000      # Starting port for mcpo instances
MCPO_TIMEOUT = 30     # Seconds to wait for mcpo startup
IDLE_TIMEOUT = 3600   # Seconds before terminating idle session (1 hour)
```

## Process Lifecycle

1. **User Request Arrives**
   - Extract Bearer token
   - Validate against dashboard

2. **Get or Create Session**
   - Check if user has existing `mcpo` instance
   - If yes and alive, reuse it
   - If no or dead, spawn new instance

3. **Spawn mcpo (if needed)**
   - Allocate port
   - Set environment variables
   - Run: `uvx mcpo --port {port} -- python mcp_server.py`
   - Wait for health check (GET /openapi.json)
   - Store in session map

4. **Route Request**
   - Forward to user's `mcpo` instance
   - Return response to client

5. **Background Cleanup**
   - Every 60 seconds
   - Terminate idle sessions (> 1 hour)

6. **Shutdown**
   - Terminate all `mcpo` instances gracefully

## Benefits

### Isolation
- Each user has their own process space
- No cross-user data leakage
- Independent resource limits

### Security
- User tokens never shared between processes
- Each `mcp_server.py` runs with its own credentials
- Process-level isolation

### Scalability
- Automatic session lifecycle management
- Idle sessions cleaned up
- Dynamic port allocation

### Debugging
- Easy to identify which process belongs to which user
- Can inspect individual user sessions
- Clear logging with user IDs

## Monitoring

**Check Active Sessions:**
```bash
curl http://localhost:8000/admin/sessions | jq
```

Output:
```json
{
  "sessions": [
    {
      "user_id": "github123",
      "port": 9000,
      "alive": true,
      "created_at": 1696435200.0,
      "last_accessed": 1696435800.0,
      "idle_seconds": 42.5
    }
  ]
}
```

**Check Logs:**
```bash
tail -f logs/auth_proxy.log
```

Look for:
- 🚀 Spawning mcpo for user X
- ✅ mcpo ready for user X  
- ♻️ Reusing existing mcpo
- 🔴 Terminating mcpo
- 🧹 Cleaning up idle session

## Troubleshooting

### mcpo fails to start

Check:
1. Is `uvx` in PATH? (`which uvx`)
2. Is `mcp_server.py` in the current directory?
3. Check logs for stderr output from failed process

### Session not reused

- Session expires after 1 hour of idle time
- Process may have died (check `is_alive` in `/admin/sessions`)

### Port conflicts

- Increase `BASE_PORT` if ports 9000+ are in use
- Check with: `lsof -i :9000-9100`

## Future Enhancements

- [ ] Add resource limits per user (CPU, memory)
- [ ] Persist sessions across proxy restarts
- [ ] Add metrics/telemetry
- [ ] Support custom timeout per user
- [ ] Add rate limiting per user
- [ ] WebSocket support for long-running connections


