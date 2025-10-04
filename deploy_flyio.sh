#!/bin/bash
# Deploy to Fly.io - Interactive Setup Script

set -e  # Exit on error

echo "🚀 A10 Hackathon Dashboard - Fly.io Deployment"
echo "=============================================="
echo ""

# Check if flyctl is installed
if ! command -v fly &> /dev/null; then
    echo "❌ flyctl not found. Installing..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
    echo "✅ flyctl installed"
fi

# Check if logged in
if ! fly auth whoami &> /dev/null; then
    echo "🔐 Please login to Fly.io..."
    fly auth login
fi

echo "✅ Logged in as: $(fly auth whoami)"
echo ""

# Check if app exists
if fly status &> /dev/null; then
    echo "📦 App already exists, will update deployment"
    APP_NAME=$(fly status --json | grep -o '"Name":"[^"]*"' | cut -d'"' -f4)
else
    echo "📦 Creating new Fly.io app..."
    fly launch --no-deploy
    APP_NAME=$(fly status --json | grep -o '"Name":"[^"]*"' | cut -d'"' -f4)
fi

echo "App name: $APP_NAME"
echo "URL: https://$APP_NAME.fly.dev"
echo ""

# Prompt for GitHub OAuth credentials
echo "🔐 GitHub OAuth Setup"
echo "---------------------"
echo "If you don't have a GitHub OAuth app yet:"
echo "1. Go to: https://github.com/settings/developers"
echo "2. Create a new OAuth App with:"
echo "   - Homepage URL: https://$APP_NAME.fly.dev"
echo "   - Callback URL: https://$APP_NAME.fly.dev/auth/callback"
echo ""

read -p "Enter your GitHub Client ID: " GITHUB_CLIENT_ID
read -sp "Enter your GitHub Client Secret: " GITHUB_CLIENT_SECRET
echo ""

# Generate session secret
SESSION_SECRET=$(openssl rand -hex 32)

echo ""
echo "🔧 Setting secrets..."
fly secrets set \
    GITHUB_CLIENT_ID="$GITHUB_CLIENT_ID" \
    GITHUB_CLIENT_SECRET="$GITHUB_CLIENT_SECRET" \
    SESSION_SECRET="$SESSION_SECRET" \
    ENABLE_AUTH="true" \
    DASHBOARD_URL="https://$APP_NAME.fly.dev" \
    --stage

echo "✅ Secrets configured"
echo ""

# Create volumes if they don't exist
echo "💾 Setting up persistent volumes..."
if ! fly volumes list | grep -q "dashboard_data"; then
    fly volumes create dashboard_data --size 1 --yes || true
fi

echo "✅ Volumes ready"
echo ""

# Deploy
echo "🚀 Deploying application..."
fly deploy --dockerfile Dockerfile.dashboard

echo ""
echo "=============================================="
echo "✅ Deployment complete!"
echo ""
echo "🌐 Dashboard URL: https://$APP_NAME.fly.dev"
echo ""
echo "📋 Next steps:"
echo "1. Visit your dashboard and login with GitHub"
echo "2. Generate an API token from the dashboard"
echo "3. Configure your MCP server with the token:"
echo ""
echo "   export MCP_API_TOKEN=\"your_token_here\""
echo "   export REQUIRE_TOKEN=\"true\""
echo "   export DASHBOARD_URL=\"https://$APP_NAME.fly.dev\""
echo ""
echo "4. Restart Claude Desktop or run MCP server"
echo ""
echo "📊 Useful commands:"
echo "  fly logs           - View application logs"
echo "  fly open           - Open dashboard in browser"
echo "  fly ssh console    - SSH into container"
echo "  fly status         - Check app status"
echo ""
echo "🎉 Happy monitoring!"

