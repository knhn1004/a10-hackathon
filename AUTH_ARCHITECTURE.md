# 🔐 Authentication Architecture

Clear explanation of how authentication works in this system.

## Two Separate Authentication Systems

### 1. Dashboard Authentication (GitHub OAuth)

**Purpose:** Secure access to the web dashboard

**Where:** Dashboard server (Fly.io or localhost)

**Flow:**
```
User → Dashboard → GitHub OAuth → User logs in → Access granted
```

**Environment Variables (Server):**
- `GITHUB_CLIENT_ID` - Set on dashboard server
- `GITHUB_CLIENT_SECRET` - Set on dashboard server
- `SESSION_SECRET` - Set on dashboard server
- `ENABLE_AUTH` - Set on dashboard server

**Who sets it:** Dashboard administrator (you)

### 2. MCP API Token Authentication

**Purpose:** Identify which user is making MCP requests

**Where:** Each user's local machine (Claude Desktop, local scripts)

**Flow:**
```
1. User logs into dashboard (GitHub OAuth)
2. User generates personal API token from dashboard
3. User copies token to their LOCAL machine
4. User configures Claude Desktop with their token
5. MCP server (running locally) sends token with requests
6. Dashboard validates token and tracks usage per user
```

**Environment Variables (User's Local Machine):**
- `MCP_API_TOKEN` - **USER sets this locally**
- `REQUIRE_TOKEN` - **USER chooses** (optional auth)
- `DASHBOARD_URL` - **USER points** to dashboard

**Who sets it:** Each individual user on their own machine

## Important: What Goes Where

### ❌ Dashboard Server DOES NOT Need

```bash
# Dashboard .env file (Fly.io)
# ❌ NOT NEEDED:
# MCP_API_TOKEN="mcp_..."  # WRONG!
```

The dashboard **validates** tokens, it doesn't **use** them!

### ✅ Dashboard Server Needs

```bash
# Dashboard .env file (Fly.io)
GITHUB_CLIENT_ID="your_github_client_id"
GITHUB_CLIENT_SECRET="your_github_client_secret"
SESSION_SECRET="$(openssl rand -hex 32)"
ENABLE_AUTH="true"
DATABASE_URL="postgresql://..."
```

### ✅ User's Local Machine Needs

```bash
# User's local .env file
MCP_API_TOKEN="mcp_abc123xyz..."  # Generated from dashboard
REQUIRE_TOKEN="true"              # Optional, enforce token
DASHBOARD_URL="https://your-dashboard.fly.dev"
```

Or in Claude Desktop config:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "MCP_API_TOKEN": "mcp_abc123xyz...",
        "REQUIRE_TOKEN": "true",
        "DASHBOARD_URL": "https://your-dashboard.fly.dev"
      }
    }
  }
}
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                 Dashboard Server                     │
│                 (Fly.io/Remote)                      │
│                                                      │
│  Environment:                                        │
│  ✓ GITHUB_CLIENT_ID                                 │
│  ✓ GITHUB_CLIENT_SECRET                             │
│  ✓ SESSION_SECRET                                   │
│  ✓ DATABASE_URL                                     │
│  ✓ ENABLE_AUTH=true                                 │
│                                                      │
│  ❌ NO MCP_API_TOKEN!                               │
│     (validates tokens, doesn't use them)            │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ HTTPS
                   │
        ┌──────────┴──────────┬──────────────────────┐
        │                     │                      │
        ▼                     ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ User A       │    │ User B       │    │ User C       │
│ (Local)      │    │ (Local)      │    │ (Local)      │
│              │    │              │    │              │
│ Claude       │    │ Claude       │    │ Claude       │
│ Desktop      │    │ Desktop      │    │ Desktop      │
│              │    │              │    │              │
│ MCP Server   │    │ MCP Server   │    │ MCP Server   │
│              │    │              │    │              │
│ Token:       │    │ Token:       │    │ Token:       │
│ mcp_abc123   │    │ mcp_xyz789   │    │ mcp_def456   │
└──────────────┘    └──────────────┘    └──────────────┘
```

## User Workflow

### Step 1: User Logs In (One Time)

```
User → https://dashboard.fly.dev
     → Click "Sign in with GitHub"
     → GitHub OAuth
     → Logged in!
```

### Step 2: User Generates Token (One Time)

```
Dashboard → Settings → API Tokens
         → Click "Generate New Token"
         → Name: "My MacBook Claude"
         → Copy token: mcp_abc123xyz...
         
⚠️  COPY NOW - Won't see it again!
```

### Step 3: User Configures Locally (One Time)

**Option A: Claude Desktop Config**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "MCP_API_TOKEN": "mcp_abc123xyz...",
        "REQUIRE_TOKEN": "true",
        "DASHBOARD_URL": "https://your-dashboard.fly.dev"
      }
    }
  }
}
```

**Option B: Local .env File**

Create `.env` in project directory:

```bash
MCP_API_TOKEN="mcp_abc123xyz..."
REQUIRE_TOKEN="true"
DASHBOARD_URL="https://your-dashboard.fly.dev"
```

### Step 4: User Uses Claude (Ongoing)

```
User: "Create a sandbox and run Python code"
      ↓
Claude Desktop
      ↓
MCP Server (local)
      ↓ [Sends token: mcp_abc123xyz...]
      ↓
Dashboard API
      ↓ [Validates token, checks: belongs to User A]
      ↓
      ✅ Valid! User: User A
      ↓
Executes code & logs:
  - User: User A
  - Action: create_sandbox
  - Timestamp: now
```

## Token Lifecycle

### Generation

```python
# Dashboard: User clicks "Generate Token"
token = f"mcp_{secrets.token_urlsafe(32)}"
token_hash = hashlib.sha256(token.encode()).hexdigest()

# Store hash in database
db.api_tokens.insert({
    "user_id": current_user.id,
    "token_hash": token_hash,  # Only hash stored!
    "name": "My MacBook",
    "active": True,
    ...
})

# Return token ONCE
return {"token": token}  # User must copy now!
```

### Validation

```python
# MCP Server: Sends token with request
response = await http_client.post(
    f"{DASHBOARD_URL}/api/tokens/validate",
    params={"token": MCP_API_TOKEN}
)

# Dashboard: Validates token
token_hash = hashlib.sha256(received_token.encode()).hexdigest()
token_record = db.api_tokens.find_one({"token_hash": token_hash})

if token_record and token_record["active"]:
    # Valid! Update usage
    token_record["usage_count"] += 1
    token_record["last_used"] = now()
    return {
        "valid": True,
        "user_id": token_record["user_id"]
    }
```

### Revocation

```python
# User revokes token from dashboard
db.api_tokens.update(
    {"token_hash": token_hash},
    {"$set": {"active": False, "revoked_at": now()}}
)

# Next MCP request with that token:
# → Validation fails
# → MCP server: "Invalid token"
# → User must generate new token
```

## Security Model

### ✅ What's Secure

1. **Tokens hashed** - SHA-256, never stored plain text
2. **One-time display** - Token shown only at generation
3. **Per-user** - Each user has their own tokens
4. **Revocable** - User can revoke anytime
5. **Trackable** - Usage logged per user
6. **HTTPS** - All communication encrypted

### ⚠️ User Responsibilities

1. **Keep token secret** - Don't share or commit to git
2. **Rotate tokens** - Generate new periodically
3. **Revoke unused** - Remove old tokens
4. **Use .env files** - Never hardcode tokens

### 🔒 Administrator Responsibilities

1. **Secure dashboard** - Enable HTTPS, OAuth
2. **Rotate secrets** - Change SESSION_SECRET periodically
3. **Monitor usage** - Check for suspicious activity
4. **Backup database** - Regular backups of token records

## Common Mistakes

### ❌ Mistake 1: Token on Server

```bash
# fly.toml or Fly.io secrets
# ❌ WRONG:
fly secrets set MCP_API_TOKEN="mcp_..."

# This makes no sense! Which user's token?
# The server validates tokens, doesn't use them!
```

### ❌ Mistake 2: Shared Token

```bash
# ❌ WRONG:
# Team shares one token in a .env.shared file

# Each user should have their own token!
# Otherwise you can't track who did what!
```

### ❌ Mistake 3: Token in Git

```bash
# .env
MCP_API_TOKEN="mcp_abc123..."

# ❌ WRONG: Commits this to git

# Always add .env to .gitignore!
```

### ✅ Correct Setup

```bash
# Dashboard (Fly.io)
fly secrets set GITHUB_CLIENT_ID="..."
fly secrets set GITHUB_CLIENT_SECRET="..."
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"

# User's local machine
# .env (gitignored)
MCP_API_TOKEN="mcp_abc123..."  # Their personal token
DASHBOARD_URL="https://dashboard.fly.dev"
```

## Summary

**Two Separate Systems:**

1. **Dashboard Auth** → GitHub OAuth → Secure web access
2. **MCP Auth** → Personal API tokens → Track user actions

**Key Points:**
- ✅ Dashboard validates tokens, doesn't use them
- ✅ Each user has their own token on their local machine
- ✅ Tokens are personal, not shared
- ✅ Tokens track who did what
- ✅ Dashboard only needs GitHub OAuth credentials

**Remember:**
> The dashboard is like a bank. Users have account numbers (tokens).
> The bank (dashboard) validates account numbers but doesn't "have" one itself!

Clear now? 😊

