# 🏠 Local Development Setup with .env

Complete guide to running the A10 Hackathon Dashboard locally using a `.env` file.

## Quick Start (No Authentication)

```bash
# 1. Install dependencies
poetry install

# 2. Copy environment template
cp .env.example .env

# 3. The default .env works as-is! Just run:
python dashboard_server.py

# 4. In another terminal:
python mcp_server.py

# 5. Visit http://localhost:8080
```

That's it! No authentication required for local dev! 🎉

## What's in the .env File?

The `.env` file loads environment variables automatically. No need to `export` manually!

### Default Configuration (No Auth)

```bash
# .env
ENABLE_AUTH="false"        # No GitHub login required
REQUIRE_TOKEN="false"      # No API tokens required
PORT="8080"                # Dashboard port
```

This is perfect for local development!

## Setup Steps

### 1. Install Dependencies

```bash
# Install Python packages
poetry install

# Or with pip
pip install -r requirements.txt

# Verify python-dotenv is installed
poetry show python-dotenv
```

### 2. Create .env File

```bash
# Copy the example
cp .env.example .env

# Or create from scratch
cat > .env << 'EOF'
# Development Settings (no auth)
ENABLE_AUTH="false"
REQUIRE_TOKEN="false"
PORT="8080"
DASHBOARD_URL="http://localhost:8080"
EOF
```

### 3. Build Docker Image (Required)

The sandbox containers need a Docker image:

```bash
# Build the code execution image
docker build -t code-sandbox:latest .

# Verify it was created
docker images | grep code-sandbox
```

### 4. Run Dashboard Server

```bash
# Start the dashboard
python dashboard_server.py

# You should see:
# INFO:dashboard:🔓 Authentication disabled
# INFO:dashboard:Starting dashboard server on http://0.0.0.0:8080
```

### 5. Run MCP Server (Optional)

```bash
# In another terminal
python mcp_server.py

# You should see:
# INFO:code-sandbox:🔓 API Token: Disabled
# INFO:code-sandbox:Starting Code Sandbox MCP Server
```

### 6. Access Dashboard

Open your browser: http://localhost:8080

No login required! 🎉

## Enable Authentication (Optional)

Want to test GitHub OAuth locally?

### 1. Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **"New OAuth App"**
3. Fill in:
   ```
   Application name: A10 Dashboard (Local)
   Homepage URL: http://localhost:8080
   Authorization callback URL: http://localhost:8080/auth/callback
   ```
4. Save the **Client ID** and **Client Secret**

### 2. Update .env File

```bash
# Edit .env
cat > .env << 'EOF'
# GitHub OAuth
GITHUB_CLIENT_ID="your_github_client_id_here"
GITHUB_CLIENT_SECRET="your_github_client_secret_here"

# Generate session secret
SESSION_SECRET="your_random_32_byte_string_here"

# Enable authentication
ENABLE_AUTH="true"

# Dashboard settings
PORT="8080"
DASHBOARD_URL="http://localhost:8080"

# MCP settings (optional)
REQUIRE_TOKEN="false"
EOF
```

### 3. Generate Session Secret

```bash
# Generate a random secret
openssl rand -hex 32

# Add it to .env
echo "SESSION_SECRET=\"$(openssl rand -hex 32)\"" >> .env
```

### 4. Restart Dashboard

```bash
# Stop the server (Ctrl+C)
# Start it again
python dashboard_server.py

# You should see:
# INFO:dashboard:🔐 GitHub OAuth enabled
```

### 5. Login

Visit http://localhost:8080 - you'll see the login page!

## Enable API Tokens

Want to test API token authentication?

### 1. Enable Auth in Dashboard

Follow steps above to enable GitHub OAuth.

### 2. Login and Generate Token

1. Login to dashboard with GitHub
2. Generate a token (we'll add UI for this)
3. Copy the token (starts with `mcp_...`)

### 3. Update .env for MCP Server

```bash
# Add to .env
echo "MCP_API_TOKEN=\"mcp_your_token_here\"" >> .env
echo "REQUIRE_TOKEN=\"true\"" >> .env
```

### 4. Restart MCP Server

```bash
python mcp_server.py

# You should see:
# INFO:code-sandbox:🔐 API Token: Configured
# INFO:code-sandbox:✅ API token validated successfully
```

## Environment Variables Reference

### Dashboard Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_AUTH` | No | `false` | Enable GitHub OAuth |
| `GITHUB_CLIENT_ID` | If auth | - | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | If auth | - | GitHub OAuth secret |
| `SESSION_SECRET` | If auth | random | Session encryption key |
| `PORT` | No | `8080` | Server port |

### MCP Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REQUIRE_TOKEN` | No | `false` | Require API token |
| `MCP_API_TOKEN` | If tokens | - | API token for auth |
| `DASHBOARD_URL` | If tokens | `localhost:8080` | Dashboard URL |
| `SANDBOX_IMAGE` | No | `code-sandbox:latest` | Docker image |
| `SANDBOX_TIMEOUT` | No | `300` | Idle timeout (seconds) |
| `MAX_SANDBOXES` | No | `10` | Max concurrent sandboxes |

## Testing Your Setup

### Test Dashboard

```bash
# Health check
curl http://localhost:8080/api/health

# Should return:
# {"status":"healthy","service":"observability-dashboard",...}
```

### Test MCP Server

```bash
# Create a test sandbox
python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from mcp_server import create_sandbox

async def test():
    result = await create_sandbox()
    print(result)

asyncio.run(test())
"
```

### Test Container Monitoring

```bash
# Check monitoring is working
curl http://localhost:8080/api/overview | jq .

# Should show system metrics
```

## Troubleshooting

### "Module not found: dotenv"

```bash
# Install python-dotenv
poetry add python-dotenv

# Or with pip
pip install python-dotenv
```

### ".env file not loading"

```bash
# Check .env file exists
ls -la .env

# Check it's in the project root
pwd
# Should be: /Users/oliver/code/a10-hackathon

# Check file contents
cat .env
```

### "OAuth callback mismatch"

Make sure GitHub OAuth app callback is: `http://localhost:8080/auth/callback`

### "Cannot connect to Docker daemon"

```bash
# Start Docker Desktop
open -a Docker

# Or check Docker is running
docker ps
```

### "Port 8080 already in use"

```bash
# Find what's using port 8080
lsof -i :8080

# Kill it or use different port
export PORT="8081"
python dashboard_server.py
```

## Development Workflow

### Typical Development Session

```bash
# Terminal 1: Dashboard
python dashboard_server.py

# Terminal 2: MCP Server (optional)
python mcp_server.py

# Terminal 3: Watch logs
tail -f logs/dashboard.log

# Terminal 4: Test commands
curl http://localhost:8080/api/overview
```

### Hot Reload

Dashboard and MCP servers don't have hot reload by default.

**Option 1: Use nodemon/watchdog**

```bash
# Install watchdog
pip install watchdog[watchmedo]

# Watch for changes
watchmedo auto-restart --pattern="*.py" --recursive -- python dashboard_server.py
```

**Option 2: Manual restart**

Just Ctrl+C and run again!

## Next Steps

1. ✅ Get local development working
2. ✅ Test without authentication
3. 🔐 (Optional) Add GitHub OAuth
4. 🎫 (Optional) Test API tokens
5. 🚀 Deploy to Fly.io when ready!

## Files to .gitignore

Add these to `.gitignore`:

```bash
# Environment and secrets
.env
.env.local

# Data files
data/api_tokens.json
*.log

# Python
__pycache__/
*.pyc
.pytest_cache/

# Virtual environments
venv/
.venv/
```

## Security Checklist

- [ ] `.env` is in `.gitignore`
- [ ] Generated strong `SESSION_SECRET`
- [ ] GitHub OAuth app uses localhost for development
- [ ] API tokens are not committed to git
- [ ] Log files don't contain secrets

## Summary

**For Local Dev:**
- ✅ Use `.env` file for configuration
- ✅ No authentication required by default
- ✅ Easy to test with or without auth
- ✅ All data stored locally in JSON files
- ✅ Fast iteration with hot reload

**When Ready:**
- 🚀 Deploy to Fly.io with production settings
- 🔐 Enable auth in production
- 🎫 Generate real API tokens
- 📊 Monitor real usage

Happy coding! 🎉

