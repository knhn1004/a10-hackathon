# Deploy to Fly.io 🚀

Complete guide to deploying the A10 Hackathon Dashboard to Fly.io with GitHub OAuth and API token authentication.

## Prerequisites

- **Fly.io account** (sign up at https://fly.io)
- **GitHub OAuth App** (create at https://github.com/settings/developers)
- **Docker** installed locally
- **flyctl** CLI installed

## Step 1: Install Fly.io CLI

```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.fly/bin:$PATH"

# Verify installation
fly version
```

## Step 2: Login to Fly.io

```bash
fly auth login
```

## Step 3: Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **"New OAuth App"**
3. Fill in:
   - **Application name**: `A10 Hackathon Dashboard`
   - **Homepage URL**: `https://your-app-name.fly.dev` (temporary, update later)
   - **Authorization callback URL**: `https://your-app-name.fly.dev/auth/callback`
4. Click **"Register application"**
5. **Save the Client ID and Client Secret** - you'll need these!

## Step 4: Initialize Fly.io App

```bash
cd /path/to/a10-hackathon

# Initialize app (this will use the existing fly.toml)
fly launch --no-deploy

# Choose a unique app name (e.g., a10-dashboard-yourname)
# Choose region closest to you
# Don't deploy yet - we need to set secrets first
```

## Step 5: Update GitHub OAuth Callback URL

Now that you have your Fly.io app name, update the GitHub OAuth App:

1. Go back to your GitHub OAuth App settings
2. Update the URLs:
   - **Homepage URL**: `https://your-actual-app-name.fly.dev`
   - **Authorization callback URL**: `https://your-actual-app-name.fly.dev/auth/callback`

## Step 6: Set Secrets

```bash
# Set GitHub OAuth credentials
fly secrets set GITHUB_CLIENT_ID="your_github_client_id"
fly secrets set GITHUB_CLIENT_SECRET="your_github_client_secret"

# Generate and set session secret (IMPORTANT!)
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"

# Enable authentication
fly secrets set ENABLE_AUTH="true"

# Optional: Set dashboard URL for token validation
fly secrets set DASHBOARD_URL="https://your-app-name.fly.dev"
```

## Step 7: Create Persistent Volumes

```bash
# Create volume for Docker socket access (if needed)
fly volumes create docker_socket --size 1

# Create volume for persistent data (logs, tokens, etc.)
fly volumes create dashboard_data --size 1
```

## Step 8: Deploy!

```bash
# Deploy the application
fly deploy

# Watch deployment logs
fly logs
```

## Step 9: Open Your Dashboard

```bash
# Open in browser
fly open

# Or visit manually
open https://your-app-name.fly.dev
```

You should see the GitHub login screen! 🎉

## Step 10: Generate API Tokens

1. **Login** to your dashboard with GitHub
2. Go to the **API Tokens** section (we'll add UI for this)
3. Click **"Generate New Token"**
4. Give it a name like "Local MCP Server"
5. **Copy the token** (you won't see it again!)

## Step 11: Use Token with MCP Server

### Option A: In Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/virtualenv/bin/python",
      "args": ["/path/to/a10-hackathon/mcp_server.py"],
      "env": {
        "MCP_API_TOKEN": "mcp_your_generated_token_here",
        "REQUIRE_TOKEN": "true",
        "DASHBOARD_URL": "https://your-app-name.fly.dev"
      }
    }
  }
}
```

### Option B: Command Line

```bash
# Export as environment variable
export MCP_API_TOKEN="mcp_your_generated_token_here"
export REQUIRE_TOKEN="true"
export DASHBOARD_URL="https://your-app-name.fly.dev"

# Run MCP server
poetry run python mcp_server.py
```

## Useful Fly.io Commands

```bash
# View logs
fly logs

# SSH into container
fly ssh console

# Check status
fly status

# Scale up/down
fly scale count 2

# View secrets
fly secrets list

# Update secret
fly secrets set KEY=value

# Deploy specific Dockerfile
fly deploy --dockerfile Dockerfile.dashboard

# Rollback
fly releases list
fly rollback <version>
```

## Troubleshooting

### Authentication Loop

If you get stuck in login loop:
```bash
# Check secrets are set
fly secrets list

# Verify GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET are correct
# Regenerate session secret
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"
```

### Can't Access Dashboard

```bash
# Check if app is running
fly status

# View recent logs
fly logs

# Check health check
fly checks list
```

### Token Validation Fails

```bash
# Ensure DASHBOARD_URL matches your Fly.io URL
fly secrets set DASHBOARD_URL="https://your-actual-app-name.fly.dev"

# Check dashboard is accessible
curl https://your-app-name.fly.dev/api/health
```

### Build Fails

```bash
# Check Dockerfile.dashboard exists
ls -la Dockerfile.dashboard

# Try local Docker build first
docker build -f Dockerfile.dashboard -t dashboard-test .

# View detailed build logs
fly deploy --verbose
```

## Monitoring & Maintenance

### View Metrics

```bash
# CPU and Memory usage
fly status

# Detailed metrics
fly dashboard metrics
```

### Update Application

```bash
# Pull latest code
git pull

# Deploy changes
fly deploy

# Zero-downtime deployment (automatic with Fly.io)
```

### Backup Data

```bash
# List volumes
fly volumes list

# Create snapshot
fly volumes snapshots create <volume_id>

# List snapshots
fly volumes snapshots list
```

## Cost Estimation

**Free Tier includes:**
- 3 shared-cpu-1x VMs
- 160GB outbound data transfer
- Automatic SSL certificates

**Your app will likely fit in free tier if:**
- Low traffic (personal/team use)
- Minimal data transfer
- Single VM deployment

**Monitor usage:**
```bash
fly dashboard billing
```

## Next Steps

1. ✅ Deploy dashboard to Fly.io
2. ✅ Login with GitHub
3. ✅ Generate API token
4. ✅ Configure MCP server with token
5. ✅ Test in Claude Desktop
6. 🎉 Start monitoring your sandboxes!

## Security Notes

- 🔒 Secrets are encrypted at rest
- 🔐 GitHub OAuth provides authentication
- 🎫 API tokens are hashed (never stored in plain text)
- 🌐 HTTPS enforced by default
- 🛡️ Session cookies are HTTP-only and secure

## Need Help?

- Fly.io Docs: https://fly.io/docs/
- Community Forum: https://community.fly.io/
- GitHub Issues: https://github.com/your-repo/issues

---

**Deployed successfully?** Share your dashboard URL (if public) and celebrate! 🎊

