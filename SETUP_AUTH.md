# Authentication Setup Guide 🔐

Complete guide to setting up GitHub OAuth and API token authentication for the A10 Hackathon Dashboard.

## Overview

The system has two layers of authentication:

1. **GitHub OAuth** - For web dashboard access (optional, can be disabled)
2. **API Tokens** - For MCP server authentication (optional, can be disabled)

## Quick Start (Development - No Auth)

For local development without authentication:

```bash
# Run dashboard without auth
python dashboard_server.py

# Run MCP server without token
python mcp_server.py
```

Access dashboard at http://localhost:8080 - no login required!

## Production Setup with GitHub OAuth

### 1. Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **"New OAuth App"**
3. Fill in:
   ```
   Application name: A10 Hackathon Dashboard
   Homepage URL: https://your-domain.com (or http://localhost:8080 for local)
   Authorization callback URL: https://your-domain.com/auth/callback
   ```
4. Save the **Client ID** and **Client Secret**

### 2. Configure Dashboard

```bash
# Set environment variables
export GITHUB_CLIENT_ID="your_client_id_here"
export GITHUB_CLIENT_SECRET="your_client_secret_here"
export SESSION_SECRET="$(openssl rand -hex 32)"
export ENABLE_AUTH="true"

# Run dashboard
python dashboard_server.py
```

### 3. Login

Visit http://localhost:8080 and click "Sign in with GitHub"!

## API Token Authentication for MCP Server

### Why API Tokens?

- Tie MCP requests to specific users
- Revoke access without changing GitHub credentials
- Track usage per token
- Multiple tokens for different clients

### Generate Tokens

#### Via Web Dashboard

1. Login to dashboard with GitHub
2. Navigate to **API Tokens** section
3. Click **"Generate New Token"**
4. Fill in:
   ```
   Name: Local MCP Server
   Description: My local development environment
   ```
5. **Copy the token** - you won't see it again!

#### Via API (cURL)

```bash
# First, get authenticated session cookie
curl -c cookies.txt http://localhost:8080/auth/github

# Generate token
curl -X POST http://localhost:8080/api/tokens/generate \
  -b cookies.txt \
  -F "name=My Token" \
  -F "description=Development" | jq .
```

### Use Token with MCP Server

#### Option A: Environment Variables

```bash
export MCP_API_TOKEN="mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export REQUIRE_TOKEN="true"
export DASHBOARD_URL="http://localhost:8080"

python mcp_server.py
```

#### Option B: Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/a10-hackathon/mcp_server.py"],
      "env": {
        "MCP_API_TOKEN": "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "REQUIRE_TOKEN": "true",
        "DASHBOARD_URL": "http://localhost:8080"
      }
    }
  }
}
```

#### Option C: .env File

Create `.env` file:

```bash
MCP_API_TOKEN=mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
REQUIRE_TOKEN=true
DASHBOARD_URL=http://localhost:8080
```

Load with:

```bash
export $(cat .env | xargs)
python mcp_server.py
```

### Manage Tokens

#### List Tokens

```bash
# Via API
curl http://localhost:8080/api/tokens \
  -b cookies.txt | jq .
```

#### Revoke Token

```bash
# Via API
curl -X POST http://localhost:8080/api/tokens/TOKEN_HASH/revoke \
  -b cookies.txt
```

#### Delete Token

```bash
# Via API
curl -X DELETE http://localhost:8080/api/tokens/TOKEN_HASH \
  -b cookies.txt
```

## Configuration Reference

### Dashboard Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_CLIENT_ID` | If auth enabled | - | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | If auth enabled | - | GitHub OAuth client secret |
| `SESSION_SECRET` | If auth enabled | random | Secret for session encryption |
| `ENABLE_AUTH` | No | `false` | Enable GitHub OAuth |
| `PORT` | No | `8080` | Dashboard port |

### MCP Server Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_API_TOKEN` | If tokens enabled | - | API token for authentication |
| `REQUIRE_TOKEN` | No | `false` | Require valid API token |
| `DASHBOARD_URL` | If tokens enabled | `http://localhost:8080` | Dashboard URL for validation |

## Security Best Practices

### Development

✅ **Do:**
- Use `ENABLE_AUTH=false` for local development
- Use `REQUIRE_TOKEN=false` for local testing
- Keep tokens in `.env` file (add to `.gitignore`)

❌ **Don't:**
- Commit tokens to git
- Share tokens publicly
- Use production tokens in development

### Production

✅ **Do:**
- Enable authentication (`ENABLE_AUTH=true`)
- Use strong session secrets (32+ bytes)
- Enable token validation (`REQUIRE_TOKEN=true`)
- Use HTTPS
- Rotate tokens periodically
- Revoke unused tokens
- Monitor token usage

❌ **Don't:**
- Use default session secrets
- Share tokens between users
- Leave tokens in logs
- Expose token endpoints publicly

## Token Storage

Tokens are stored in `data/api_tokens.json`:

```json
{
  "sha256_hash_of_token": {
    "user_id": "github_username",
    "name": "My Token",
    "description": "For local dev",
    "created_at": 1234567890.0,
    "last_used": 1234567899.0,
    "usage_count": 42,
    "active": true
  }
}
```

**Security Notes:**
- Actual tokens are **never stored** - only SHA-256 hashes
- Tokens are shown **only once** during generation
- Users can only see/manage their own tokens
- Revoked tokens stay in file but are marked inactive

## Troubleshooting

### "OAuth callback mismatch" Error

**Problem:** GitHub OAuth redirect URL doesn't match

**Solution:**
1. Check GitHub OAuth app settings
2. Ensure callback URL matches: `https://your-domain.com/auth/callback`
3. Include port for local dev: `http://localhost:8080/auth/callback`

### "Invalid API token" Error

**Problem:** MCP server can't validate token

**Solutions:**
1. Check token is copied correctly (starts with `mcp_`)
2. Ensure dashboard is running and accessible
3. Verify `DASHBOARD_URL` matches actual dashboard URL
4. Check token hasn't been revoked
5. Try generating a new token

### "Not authenticated" Error

**Problem:** Can't access dashboard or API

**Solutions:**
1. Login with GitHub OAuth
2. Check session cookie is being set
3. Verify `SESSION_SECRET` is configured
4. Clear browser cookies and login again

### Token Validation Timeout

**Problem:** MCP server times out validating token

**Solutions:**
1. Check dashboard is running: `curl http://localhost:8080/api/health`
2. Verify network connectivity
3. Check firewall/proxy settings
4. Increase timeout in code if needed

## Migration Guide

### From No Auth to GitHub OAuth

```bash
# 1. Create GitHub OAuth app (see above)

# 2. Set environment variables
export GITHUB_CLIENT_ID="..."
export GITHUB_CLIENT_SECRET="..."
export SESSION_SECRET="$(openssl rand -hex 32)"
export ENABLE_AUTH="true"

# 3. Restart dashboard
pkill -f dashboard_server.py
python dashboard_server.py

# 4. Login with GitHub
# All existing data is preserved!
```

### From No Tokens to API Tokens

```bash
# 1. Generate token from dashboard

# 2. Configure MCP server
export MCP_API_TOKEN="mcp_..."
export REQUIRE_TOKEN="true"

# 3. Restart MCP server
# Update Claude Desktop config if needed
```

## FAQ

**Q: Can I use without GitHub OAuth?**  
A: Yes! Set `ENABLE_AUTH=false` or don't set GitHub credentials.

**Q: Can I use without API tokens?**  
A: Yes! Set `REQUIRE_TOKEN=false` in MCP server.

**Q: Can I use both features independently?**  
A: Yes! Dashboard auth and MCP tokens are independent.

**Q: How many tokens can I create?**  
A: Unlimited! Create tokens for each client/environment.

**Q: Can I share tokens?**  
A: Technically yes, but not recommended. Each user should have their own tokens.

**Q: What happens if token is stolen?**  
A: Revoke it immediately from the dashboard. Generate a new one.

**Q: Can I use with multiple dashboards?**  
A: Yes! Set different `DASHBOARD_URL` for different environments.

**Q: Does it work with Fly.io?**  
A: Yes! See `DEPLOY_FLYIO.md` for deployment guide.

---

Need more help? Check the full documentation or open an issue! 🚀

