#!/bin/bash
# Restart all services with updated dependencies (using Poetry environment)

echo "🔄 Restarting Code Sandbox Services"
echo "===================================="
echo ""

# Stop existing services
echo "1️⃣  Stopping existing services..."
pkill -f "python.*mcp_server" 2>/dev/null
pkill -f "python.*dashboard_server" 2>/dev/null
pkill -f "python.*monitor.py" 2>/dev/null
sleep 2
echo "   ✅ Stopped old services"

echo ""
echo "2️⃣  Verifying dependencies..."

# Check if langchain is installed
if poetry run python -c "import langchain_ollama" 2>/dev/null; then
    echo "   ✅ LangChain packages installed"
else
    echo "   ❌ LangChain packages missing!"
    echo "      Run: poetry install"
    exit 1
fi

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✅ Ollama is running"
else
    echo "   ❌ Ollama is not running"
    echo "      Start it with: ollama serve"
    echo "      Or in background: nohup ollama serve > /dev/null 2>&1 &"
    exit 1
fi

# Check if llama3.1 model exists
if ollama list 2>/dev/null | grep -q "llama3.1"; then
    echo "   ✅ llama3.1 model available"
else
    echo "   ⚠️  llama3.1 model not found"
    echo "      Pull it with: ollama pull llama3.1:latest"
    echo "      This may take a few minutes..."
    # Optionally auto-pull:
    # ollama pull llama3.1:latest
fi

# Check ML model
if [ -f "models/mining_detector.pkl" ]; then
    echo "   ✅ ML model exists"
else
    echo "   ⚠️  ML model not found at models/mining_detector.pkl"
fi

echo ""
echo "3️⃣  Starting services..."

# Start dashboard server
echo "   Starting dashboard server..."
poetry run python dashboard_server.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
sleep 2

if kill -0 $DASHBOARD_PID 2>/dev/null; then
    echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"
else
    echo "   ❌ Dashboard failed to start"
    echo "      Check logs/dashboard.log"
    exit 1
fi

# Start MCP server
echo "   Starting MCP server..."
poetry run python mcp_server.py > logs/mcp.log 2>&1 &
MCP_PID=$!
sleep 2

if kill -0 $MCP_PID 2>/dev/null; then
    echo "   ✅ MCP server started (PID: $MCP_PID)"
else
    echo "   ❌ MCP server failed to start"
    echo "      Check logs/mcp.log"
    exit 1
fi

echo ""
echo "===================================="
echo "✅ Services Started Successfully!"
echo "===================================="
echo ""
echo "📊 Dashboard:  http://localhost:8080"
echo "🔌 MCP Server: Running (stdio)"
echo ""
echo "📝 Logs:"
echo "   Dashboard: tail -f logs/dashboard.log"
echo "   MCP:       tail -f logs/mcp.log"
echo ""
echo "🛑 To stop services:"
echo "   pkill -f mcp_server"
echo "   pkill -f dashboard_server"
echo ""
echo "💡 Test the system:"
echo "   1. Use Claude to execute code via MCP"
echo "   2. Check LLM Reviews tab in dashboard"
echo "   3. Execute mining-like code for ML detection"
echo "   4. Check ML Model tab in dashboard"
echo ""

