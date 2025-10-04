# Multi-User MCP Deployment Guide

## Overview

This setup exposes your MCP server to **multiple users**, each authenticating with their own personal dashboard token. There's **no global token** required - each request is validated independently!

## Architecture

```
┌─────────────────┐
│  ChatGPT User A │──┐
└─────────────────┘  │  Bearer: token_A
                     │
┌─────────────────┐  │     ┌──────────────┐     ┌──────────┐     ┌─────────────┐
│  ChatGPT User B │──┼────>│ Auth Proxy   │────>│   MCPO   │────>│ MCP Server  │
└─────────────────┘  │     │ (port 8000)  │     │ (port    │     │  (stdio)    │
                     │     │              │     │  8001)   │     │             │
┌─────────────────┐  │     └──────┬───────┘     └──────────┘     └─────────────┘
│  ChatGPT User C │──┘            │
└─────────────────┘   Bearer:     │
                      token_C     │ validates each token
                                  ▼
                           ┌──────────────┐
                           │  Dashboard   │
                           │ (port 8080)  │
                           └──────────────┘
```

## How It Works

### 1. **No Global Token Needed**
- When running `./run_with_cloudflare.sh`, you don't need to set `MCP_API_TOKEN`
- Each user brings their own token when they configure ChatGPT
- The auth proxy validates each token on every request

### 2. **Auth Proxy Layer**
- Intercepts all incoming requests on port 8000
- Extracts the `Authorization: Bearer <token>` header
- Validates the token against your dashboard API
- Only forwards valid requests to MCPO backend

### 3. **Per-Request Validation**
- User A makes a request → Auth proxy validates token_A → Forwards to MCPO
- User B makes a request → Auth proxy validates token_B → Forwards to MCPO
- Invalid token → 401 Unauthorized (never reaches MCP server)

### 4. **Dashboard Tracks Everything**
- Each user generates their token from the dashboard
- Dashboard logs which user made which request
- All activity is tracked per-user for audit purposes

## Deployment Steps

### Step 1: Run the Dashboard
```bash
./run_dashboard.sh
```

This creates the token management interface at `http://localhost:8080`.

### Step 2: Start Multi-User Server
```bash
./run_with_cloudflare.sh
```

**No need to set MCP_API_TOKEN!** The script will:
- Start MCPO backend on port 8001
- Start Auth Proxy on port 8000
- Start Cloudflare Tunnel to expose port 8000
- Display the public URL

### Step 3: Users Generate Tokens
Each user:
1. Goes to your dashboard (e.g., `http://localhost:8080` or public dashboard URL)
2. Logs in or creates account
3. Generates a personal API token
4. Copies their token for ChatGPT

### Step 4: Users Configure ChatGPT
Each user:
1. Goes to https://chat.openai.com
2. Creates a Custom GPT → Actions
3. Imports OpenAPI from: `https://your-domain.com/openapi.json`
4. Sets Authentication:
   - Type: **Bearer Token**
   - Token: **[Their personal token from step 3]**

## Testing

### Test 1: Verify Dashboard
```bash
./test_auth_proxy.sh
```

This checks:
- ✅ Dashboard API is running
- ✅ Test token is valid
- ✅ MCPO backend is ready
- ✅ Auth proxy is ready

### Test 2: Verify Public Access
```bash
# With valid token (should succeed)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-domain.com/openapi.json

# Without token (should fail with 401)
curl https://your-domain.com/openapi.json
```

### Test 3: Test in ChatGPT
Ask your Custom GPT:
> "Create a Python sandbox and calculate the factorial of 10"

You should see:
- ChatGPT makes API call with your token
- Auth proxy validates your token
- MCP server executes the code
- Result returned to ChatGPT

## Multi-User Benefits

### ✅ Secure
- Each user has their own token
- Tokens can be revoked individually
- Invalid tokens are rejected before reaching your server

### ✅ Accountable
- Dashboard tracks which user made which request
- Audit trail for all API calls
- Easy to identify and revoke problematic users

### ✅ Scalable
- Supports unlimited users
- No shared secrets
- Each user manages their own credentials

### ✅ Flexible
- Users can rotate their tokens independently
- Different tokens can have different permissions (future)
- Central token management via dashboard

## Monitoring

### Logs
All activity is logged to separate files:
```bash
tail -f logs/auth_proxy.log   # Token validation
tail -f logs/mcpo.log          # API requests
tail -f logs/mcp.log           # MCP operations
tail -f logs/cloudflare.log    # Tunnel status
```

### Dashboard
Your dashboard (`http://localhost:8080`) shows:
- Active tokens
- Request history per user
- Token usage statistics
- Execution logs

## Troubleshooting

### "401 Unauthorized" in ChatGPT
- **Cause**: Invalid or expired token
- **Fix**: User regenerates token from dashboard and updates ChatGPT

### "502 Bad Gateway"
- **Cause**: Auth proxy can't reach MCPO or dashboard
- **Fix**: Check that all services are running (`ps aux | grep -E "mcpo|auth_proxy|dashboard"`)

### Token validation fails
- **Cause**: Dashboard not running or not accessible
- **Fix**: Start dashboard with `./run_dashboard.sh`

### Cloudflare tunnel not starting
- **Cause**: `cloudflared` not installed or not logged in
- **Fix**: 
  ```bash
  brew install cloudflared
  cloudflared tunnel login
  ```

## Security Best Practices

### 1. **Use HTTPS**
- Cloudflare Tunnel automatically provides HTTPS
- Never expose port 8000 directly without TLS

### 2. **Rotate Tokens Regularly**
- Encourage users to rotate tokens every 90 days
- Revoke tokens when users leave

### 3. **Monitor Dashboard**
- Check logs regularly for suspicious activity
- Set up alerts for unusual API usage

### 4. **Limit Token Scope** (Future Enhancement)
- Implement token permissions
- Allow read-only vs. execute tokens
- Rate limit per token

## Comparison: Single-User vs. Multi-User

| Feature | Single-User (Claude Desktop) | Multi-User (ChatGPT via Cloudflare) |
|---------|------------------------------|--------------------------------------|
| **Token** | One global `MCP_API_TOKEN` | Each user has their own token |
| **Transport** | stdio (local only) | HTTP (public) |
| **Auth** | Env var | Bearer token per request |
| **Scale** | 1 user | Unlimited users |
| **Audit** | Basic logging | Per-user tracking |
| **Setup** | `./run_dashboard.sh` | `./run_with_cloudflare.sh` |

## Summary

This multi-user setup is production-ready and:
- ✅ **No global token required** - each user manages their own
- ✅ **Per-request validation** - every call is authenticated
- ✅ **Fully auditable** - dashboard tracks all activity
- ✅ **Scalable** - supports any number of users
- ✅ **Secure** - HTTPS via Cloudflare, token validation at edge

Users simply generate a token from your dashboard, configure it in ChatGPT, and they're ready to go! 🚀

