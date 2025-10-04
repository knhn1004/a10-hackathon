#!/bin/bash
# Run MCP server with Cloudflare Tunnel for ChatGPT integration
# This exposes your MCP server publicly via Cloudflare's network

set -e

echo "🌐 Starting MCP Server with Cloudflare Tunnel"
echo "=============================================="
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "❌ Error: cloudflared is not installed"
    echo ""
    echo "Install it with:"
    echo "  macOS:   brew install cloudflared"
    echo "  Linux:   Download from https://github.com/cloudflare/cloudflared/releases"
    echo ""
    echo "Then run: cloudflared tunnel login"
    exit 1
fi

# Info about multi-user setup
echo "ℹ️  Multi-User Setup"
echo "   This exposes your MCP server for multiple users."
echo "   Each user authenticates with their own dashboard token."
echo "   No global MCP_API_TOKEN needed!"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if sandbox image exists
if ! docker images | grep -q "code-sandbox"; then
    echo "📦 Building code-sandbox Docker image..."
    docker build -t code-sandbox:latest .
else
    echo "✅ Found code-sandbox Docker image"
fi

echo ""
echo "🚀 Starting MCP server with mcpo on port 8000..."
echo ""

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8000 is already in use!"
    read -p "Kill the existing process? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
        echo "✅ Port 8000 freed"
    else
        echo "❌ Cannot start server on port 8000"
        exit 1
    fi
fi

# Get Python path
PYTHON_PATH=$(poetry env info -p)/bin/python
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create logs directory
mkdir -p logs

# Start mcpo backend (NO auth - proxy handles it)
echo "Starting MCPO backend on port 8001 (no auth)..."
uvx mcpo --port 8001 -- "$PYTHON_PATH" "$SCRIPT_DIR/mcp_server.py" > logs/mcpo.log 2>&1 &
MCPO_PID=$!

sleep 2

# Start auth proxy on port 8000
echo "Starting auth proxy on port 8000..."
"$PYTHON_PATH" "$SCRIPT_DIR/auth_proxy.py" > logs/auth_proxy.log 2>&1 &
PROXY_PID=$!

# Update cleanup trap
trap "kill $MCPO_PID $PROXY_PID 2>/dev/null" EXIT

# Give mcpo time to start
sleep 3

# Check if both started successfully
if ! kill -0 $MCPO_PID 2>/dev/null; then
    echo "❌ Error: MCPO backend failed to start"
    echo "Check logs/mcpo.log for details"
    tail -20 logs/mcpo.log
    exit 1
fi

if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "❌ Error: Auth proxy failed to start"
    echo "Check logs/auth_proxy.log for details"
    tail -20 logs/auth_proxy.log
    exit 1
fi

echo "✅ MCP server with auth proxy running on http://localhost:8000"
echo "   Auth Proxy: logs/auth_proxy.log"
echo "   MCPO Backend: logs/mcpo.log"
echo ""

# Ask user for tunnel type
echo "Choose tunnel type:"
echo "  1) Quick temporary tunnel (easiest, URL changes each time)"
echo "  2) Named persistent tunnel (recommended for production)"
echo ""
read -p "Enter choice (1 or 2): " -n 1 -r
echo
echo ""

if [[ $REPLY == "2" ]]; then
    # Named tunnel
    echo "📝 Setting up named tunnel..."
    echo ""
    
    # Check if user has logged in
    if [ ! -f ~/.cloudflared/cert.pem ]; then
        echo "❌ Not authenticated with Cloudflare"
        echo ""
        echo "Run first: cloudflared tunnel login"
        echo "Then try again"
        kill $MCPO_PID
        exit 1
    fi
    
    # Ask for tunnel name
    read -p "Enter tunnel name (default: mcp-chatgpt): " TUNNEL_NAME
    TUNNEL_NAME=${TUNNEL_NAME:-mcp-chatgpt}
    
    # Check if tunnel exists, get tunnel ID
    TUNNEL_ID=""
    if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
        echo "✅ Using existing tunnel: $TUNNEL_NAME"
        TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
    else
        echo "📝 Creating new tunnel: $TUNNEL_NAME"
        cloudflared tunnel create "$TUNNEL_NAME" 2>&1 | tee /tmp/tunnel_create.log
        TUNNEL_ID=$(grep -Eo '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' /tmp/tunnel_create.log | head -1)
    fi
    
    echo ""
    echo "🌐 Configuring DNS..."
    echo ""
    
    # Get list of zones/domains from Cloudflare
    echo "Fetching your Cloudflare domains..."
    
    # Try to get zones (requires cf API, might not work with just cert.pem)
    # Let user enter domain or use without domain
    echo ""
    echo "Choose domain setup:"
    echo "  1) Enter a domain you own on Cloudflare"
    echo "  2) Skip domain (use tunnel ID URL)"
    echo ""
    read -p "Enter choice (1 or 2): " -n 1 -r DOMAIN_CHOICE
    echo ""
    echo ""
    
    HOSTNAME=""
    if [[ $DOMAIN_CHOICE == "1" ]]; then
        read -p "Enter your domain (e.g., example.com): " DOMAIN
        read -p "Enter subdomain (default: mcp): " SUBDOMAIN
        SUBDOMAIN=${SUBDOMAIN:-mcp}
        HOSTNAME="$SUBDOMAIN.$DOMAIN"
        
        echo ""
        echo "📝 Creating DNS route: $HOSTNAME → $TUNNEL_NAME"
        
        if cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME" 2>&1 | tee /tmp/dns_route.log; then
            echo "✅ DNS route created successfully"
        else
            echo "⚠️  DNS route may already exist or failed"
            cat /tmp/dns_route.log
        fi
    else
        echo "ℹ️  Skipping DNS configuration"
        echo "   You can configure it later in Cloudflare Zero Trust dashboard"
        HOSTNAME="<tunnel-id>.cfargotunnel.com"
    fi
    
    # Create config file
    echo ""
    echo "📝 Creating tunnel configuration..."
    
    mkdir -p ~/.cloudflared
    
    # Find credentials file
    CRED_FILE=""
    if [ -n "$TUNNEL_ID" ]; then
        CRED_FILE="$HOME/.cloudflared/$TUNNEL_ID.json"
    else
        # Try to find it
        CRED_FILE=$(ls ~/.cloudflared/*.json 2>/dev/null | head -1)
    fi
    
    if [ -f "$CRED_FILE" ]; then
        cat > ~/.cloudflared/config.yml <<EOF
tunnel: $TUNNEL_NAME
credentials-file: $CRED_FILE

ingress:
  - hostname: $HOSTNAME
    service: http://localhost:8000
  - service: http_status:404
EOF
        echo "✅ Config created at ~/.cloudflared/config.yml"
    else
        echo "⚠️  Could not find credentials file. You may need to configure manually."
    fi
    
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "✨ Tunnel configured and starting!"
    echo "════════════════════════════════════════════════════════"
    echo ""
    if [[ $DOMAIN_CHOICE == "1" ]]; then
        echo "Public URL: https://$HOSTNAME"
        echo ""
        echo "📋 To configure ChatGPT Custom GPT:"
        echo "  1. Each user generates their token at:"
        echo "     http://localhost:8080 (or your dashboard URL)"
        echo "  2. Go to: https://chat.openai.com"
        echo "  3. Create Custom GPT → Actions"
        echo "  4. Import OpenAPI from:"
        echo "     https://$HOSTNAME/openapi.json"
        echo "  5. Authentication:"
        echo "     • Type: Bearer Token"
        echo "     • Token: [User's personal dashboard token]"
        echo "     • Multi-user: ✅ Each request validated separately!"
    else
        echo "Check Cloudflare Zero Trust dashboard for your tunnel URL:"
        echo "  https://one.dash.cloudflare.com/"
        echo "  → Networks → Tunnels → $TUNNEL_NAME"
    fi
    echo ""
    echo "📊 Logs saved to:"
    echo "  • Auth Proxy: logs/auth_proxy.log"
    echo "  • MCPO Backend: logs/mcpo.log"
    echo "  • MCP Server: logs/mcp.log"
    echo "  • Cloudflare Tunnel: logs/cloudflare.log"
    echo ""
    echo "Press Ctrl+C to stop both services"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Set up trap for cleanup
    trap "echo ''; echo '🛑 Stopping services...'; kill $MCPO_PID $PROXY_PID 2>/dev/null; echo '✅ Stopped'; exit 0" INT TERM
    
    # Run the tunnel with output redirected to log
    cloudflared tunnel run "$TUNNEL_NAME" >> logs/cloudflare.log 2>&1
    
    # If cloudflared exits normally, clean up
    kill $MCPO_PID $PROXY_PID 2>/dev/null
    exit 0
    
elif [[ $REPLY == "1" ]]; then
    # Quick tunnel
    echo "🌐 Starting quick tunnel..."
    echo ""
    echo "⏳ Please wait, getting your public URL..."
    echo ""
    
    # Create a temp file for cloudflared output
    CF_LOG=$(mktemp)
    
    # Run cloudflared in background and capture output
    cloudflared tunnel --url http://localhost:8000 > "$CF_LOG" 2>&1 &
    CF_PID=$!
    
    # Wait for URL to appear in log (max 30 seconds)
    URL=""
    for i in {1..30}; do
        if [ -f "$CF_LOG" ]; then
            # Try to extract URL from log
            URL=$(grep -Eo 'https://[a-zA-Z0-9._-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | head -1)
            
            if [ -n "$URL" ]; then
                break
            fi
        fi
        sleep 1
        echo -n "."
    done
    echo ""
    
    if [ -z "$URL" ]; then
        echo "❌ Failed to get tunnel URL. Check logs/cloudflare.log"
        cat "$CF_LOG" > logs/cloudflare.log
        rm -f "$CF_LOG"
        kill $MCPO_PID 2>/dev/null
        exit 1
    fi
    
    # Save cloudflared logs
    cp "$CF_LOG" logs/cloudflare.log
    
    # Show success message
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "✨ Your MCP server is now public!"
    echo "════════════════════════════════════════════════════════"
    echo ""
    echo "Public URL: $URL"
    echo ""
    echo "📋 To configure ChatGPT Custom GPT:"
    echo "  1. Each user generates their token at:"
    echo "     http://localhost:8080 (or your dashboard URL)"
    echo "  2. Go to: https://chat.openai.com"
    echo "  3. Create Custom GPT → Actions"
    echo "  4. Import OpenAPI from:"
    echo "     $URL/openapi.json"
    echo "  5. Authentication:"
    echo "     • Type: Bearer Token"
    echo "     • Token: [User's personal dashboard token]"
    echo "     • Multi-user: ✅ Each request validated separately!"
    echo ""
    echo "🔍 Test your endpoints:"
    echo "  • API Docs: $URL/docs"
    echo "  • OpenAPI Spec: $URL/openapi.json"
    echo ""
    echo "📊 Monitor requests:"
    echo "  • Local Dashboard: http://localhost:8080"
    echo "  • Auth Proxy: logs/auth_proxy.log"
    echo "  • MCPO Backend: logs/mcpo.log"
    echo "  • MCP Server: logs/mcp.log"
    echo "  • Cloudflare Tunnel: logs/cloudflare.log"
    echo ""
    echo "⚠️  Note: This URL is temporary and will change when you restart"
    echo "   For a permanent URL, use a named tunnel (option 2)"
    echo ""
    echo "💡 Tunnel running in background. Press Ctrl+C to stop."
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Tail cloudflared logs quietly in background
    tail -f "$CF_LOG" >> logs/cloudflare.log 2>&1 &
    TAIL_PID=$!
    
    # Update trap to clean up cloudflared and tail
    trap "echo ''; echo '🛑 Stopping services...'; kill $MCPO_PID $PROXY_PID $CF_PID $TAIL_PID 2>/dev/null; rm -f '$CF_LOG'; echo '✅ Stopped'; exit 0" INT TERM
    
    # Wait for signals
    wait
fi

