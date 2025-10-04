#!/bin/bash
# Production deployment script for MCP Server
# Works on any VPS (DigitalOcean, AWS EC2, etc.)

set -e

echo "🚀 Starting MCP Server Deployment"
echo "=================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if code-sandbox image exists
if ! docker images | grep -q "code-sandbox"; then
    echo "📦 Building code-sandbox Docker image..."
    docker build -t code-sandbox:latest .
else
    echo "✅ Found code-sandbox Docker image"
fi

# Create logs directory
mkdir -p logs

# Get Python path
PYTHON_PATH=$(poetry env info -p)/bin/python
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start Dashboard
echo "Starting Dashboard on port 8080..."
python3 "$SCRIPT_DIR/dashboard_server.py" > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✅ Dashboard started (PID: $DASHBOARD_PID)"

# Wait for dashboard
sleep 3

# Start MCPO backend (internal)
echo "Starting MCPO backend on port 8001..."
uvx mcpo --port 8001 -- "$PYTHON_PATH" "$SCRIPT_DIR/mcp_server.py" > logs/mcpo.log 2>&1 &
MCPO_PID=$!
echo "✅ MCPO started (PID: $MCPO_PID)"

# Wait for MCPO
sleep 3

# Start Auth Proxy (public)
echo "Starting Auth Proxy on port 8000..."
python3 "$SCRIPT_DIR/auth_proxy.py" > logs/auth_proxy.log 2>&1 &
PROXY_PID=$!
echo "✅ Auth Proxy started (PID: $PROXY_PID)"

# Wait for auth proxy
sleep 2

# Get public IP (works on most cloud providers)
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "════════════════════════════════════════════════════════"
echo "✨ MCP Server Running!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "📋 Local URLs:"
echo "  • Dashboard: http://localhost:8080"
echo "  • Auth Proxy: http://localhost:8000"
echo "  • MCPO Backend: http://localhost:8001 (internal)"
echo ""
echo "🌐 Public URLs:"
echo "  • Dashboard: http://$PUBLIC_IP:8080"
echo "  • OpenAPI Spec: http://$PUBLIC_IP:8000/openapi.json"
echo "  • API Endpoint: http://$PUBLIC_IP:8000"
echo ""
echo "📋 ChatGPT Configuration:"
echo "  1. Go to: https://chat.openai.com"
echo "  2. Create Custom GPT → Actions"
echo "  3. Import OpenAPI from:"
echo "     http://$PUBLIC_IP:8000/openapi.json"
echo "  4. Authentication:"
echo "     • Type: Bearer Token"
echo "     • Token: [User generates from dashboard]"
echo ""
echo "🔑 Generate Tokens:"
echo "  1. Open: http://$PUBLIC_IP:8080"
echo "  2. Each user creates account and generates token"
echo "  3. Use token in ChatGPT configuration"
echo ""
echo "📊 Monitor Logs:"
echo "  • Auth Proxy: tail -f logs/auth_proxy.log"
echo "  • MCPO Backend: tail -f logs/mcpo.log"
echo "  • Dashboard: tail -f logs/dashboard.log"
echo "  • MCP Server: tail -f logs/mcp.log"
echo ""
echo "🛑 To stop all services:"
echo "  kill $DASHBOARD_PID $MCPO_PID $PROXY_PID"
echo ""
echo "💡 Press Ctrl+C to stop all services"
echo "════════════════════════════════════════════════════════"
echo ""

# Set up trap for cleanup
trap "echo ''; echo '🛑 Stopping services...'; kill $DASHBOARD_PID $MCPO_PID $PROXY_PID 2>/dev/null; echo '✅ All services stopped'; exit 0" INT TERM

# Wait for signals
wait

