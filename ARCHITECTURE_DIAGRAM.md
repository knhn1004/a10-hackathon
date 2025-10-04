# Per-User MCP Architecture Diagram

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Auth Proxy (Port 8000)                         │
│                                                                           │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐ │
│  │  Token          │    │  Session         │    │  Process           │ │
│  │  Validation     │───▶│  Management      │───▶│  Spawning          │ │
│  │  (Dashboard)    │    │  (user_sessions) │    │  (mcpo + mcp)      │ │
│  └─────────────────┘    └──────────────────┘    └────────────────────┘ │
│           │                      │                         │             │
│           │                      │                         │             │
│           ▼                      ▼                         ▼             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Request Router (Middleware)                        │   │
│  │  Routes authenticated requests to user's mcpo instance          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                │ Forwards to user-specific mcpo
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ mcpo (port 9000)  │   │ mcpo (port 9001)  │   │ mcpo (port 9002)  │
│                   │   │                   │   │                   │
│ ENV:              │   │ ENV:              │   │ ENV:              │
│  USER_ID=user1    │   │  USER_ID=user2    │   │  USER_ID=user3    │
│  MCP_API_TOKEN=   │   │  MCP_API_TOKEN=   │   │  MCP_API_TOKEN=   │
│    abc123...      │   │    def456...      │   │    ghi789...      │
│                   │   │                   │   │                   │
│       │           │   │       │           │   │       │           │
│       ▼           │   │       ▼           │   │       ▼           │
│ ┌─────────────┐   │   │ ┌─────────────┐   │   │ ┌─────────────┐   │
│ │mcp_server.py│   │   │ │mcp_server.py│   │   │ │mcp_server.py│   │
│ └─────────────┘   │   │ └─────────────┘   │   │ └─────────────┘   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

## Request Flow

```
1. USER REQUEST
   │
   │ GET /v1/mcp/list-tools
   │ Authorization: Bearer abc123...
   │
   ▼
2. AUTH PROXY
   │
   ├─► Validate token with dashboard
   │   └─► Returns: {valid: true, user_id: "user1"}
   │
   ├─► Check session map
   │   └─► user_sessions["user1"] exists?
   │
   ├─► NO: Spawn new mcpo
   │   │   ├─► Allocate port (9000)
   │   │   ├─► Set ENV variables
   │   │   ├─► Run: uvx mcpo --port 9000 -- python mcp_server.py
   │   │   ├─► Wait for health check
   │   │   └─► Store in user_sessions
   │   │
   │   └─► YES: Reuse existing mcpo
   │       └─► Update last_accessed timestamp
   │
   ├─► Route request to http://localhost:9000/v1/mcp/list-tools
   │
   ▼
3. MCPO INSTANCE (user1's)
   │
   ├─► Forwards to mcp_server.py
   │
   ▼
4. MCP_SERVER.PY
   │
   ├─► Executes tool listing
   ├─► Has access to MCP_API_TOKEN from ENV
   │
   ▼
5. RESPONSE
   │
   ├─► mcpo ──▶ Auth Proxy ──▶ User
   │
   └─► {"tools": [...]}
```

## Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Session Lifecycle                              │
└─────────────────────────────────────────────────────────────────────┘

NEW USER REQUEST
      │
      ▼
┌──────────────┐
│ Spawn mcpo   │  Port: 9000, created_at: T0, last_accessed: T0
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Active       │  User makes requests
│ Session      │  last_accessed updated on each request
└──────┬───────┘
       │
       ├─► Continue Activity
       │   └─► last_accessed keeps updating
       │
       └─► Idle for 60+ minutes
           │
           ▼
      ┌──────────────┐
      │ Cleanup Task │  Runs every 60 seconds
      │ Detects Idle │  Checks: now - last_accessed > 3600s
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ Terminate    │  process.terminate()
      │ Release Port │  used_ports.remove(9000)
      │ Remove Entry │  del user_sessions["user1"]
      └──────────────┘
```

## Data Structures

```python
# Global state
user_sessions: Dict[str, McpoInstance] = {
    "user1": McpoInstance(
        user_id="user1",
        token="abc123...",
        port=9000,
        process=<Popen object>,
        created_at=1696435200.0,
        last_accessed=1696435800.0
    ),
    "user2": McpoInstance(
        user_id="user2",
        token="def456...",
        port=9001,
        process=<Popen object>,
        created_at=1696435300.0,
        last_accessed=1696435900.0
    )
}

used_ports: Set[int] = {9000, 9001}
```

## Port Allocation

```
┌─────────────────────────────────────────────┐
│          Port Allocation Strategy           │
└─────────────────────────────────────────────┘

BASE_PORT = 9000

User 1 arrives → Allocate 9000 → used_ports.add(9000)
User 2 arrives → Allocate 9001 → used_ports.add(9001)
User 3 arrives → Allocate 9002 → used_ports.add(9002)

User 1 idle → Terminate → Release 9000 → used_ports.remove(9000)

User 4 arrives → Allocate 9000 (reused) → used_ports.add(9000)
```

## Environment Variable Flow

```
┌─────────────┐
│ User Token  │ "Bearer abc123..."
└──────┬──────┘
       │
       │ Validated by dashboard
       │
       ▼
┌─────────────┐
│ Auth Proxy  │ Extracts token: "abc123..."
└──────┬──────┘
       │
       │ Spawns mcpo with ENV
       │
       ▼
┌────────────────────────────┐
│ mcpo Process               │
│                            │
│ ENV:                       │
│   MCP_API_TOKEN=abc123...  │◄─── Passed to child
│   USER_ID=user1            │
│   DASHBOARD_URL=...        │
└─────────────┬──────────────┘
              │
              │ Executes: python mcp_server.py
              │
              ▼
┌────────────────────────────┐
│ mcp_server.py              │
│                            │
│ os.getenv("MCP_API_TOKEN") │◄─── Reads from ENV
│ >>> "abc123..."            │
└────────────────────────────┘
```

## Monitoring Points

```
┌────────────────────────────────────────────────────────────────┐
│                     Monitoring Endpoints                       │
└────────────────────────────────────────────────────────────────┘

GET /proxy-health
    └─► {"status": "ok", "active_sessions": 2}

GET /admin/sessions
    └─► {
          "sessions": [
            {
              "user_id": "user1",
              "port": 9000,
              "alive": true,
              "created_at": 1696435200.0,
              "last_accessed": 1696435800.0,
              "idle_seconds": 42.5
            }
          ]
        }

Logs: logs/auth_proxy.log
    └─► 🚀 Spawning mcpo for user user1 on port 9000
    └─► ✅ mcpo ready for user user1 on port 9000
    └─► ♻️  Reusing existing mcpo for user user1 on port 9000
    └─► 🧹 Cleaning up idle session for user user1
    └─► 🔴 Terminating mcpo for user user1 (port 9000)
```


