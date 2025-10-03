#!/bin/bash
# Run MCP Code Sandbox Server through mcpo proxy for Open WebUI
# This exposes the MCP server as REST API endpoints

set -e

echo "🚀 Starting MCP Code Sandbox with mcpo proxy"
echo "=============================================="
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

# Set Python path to use poetry's virtualenv
PYTHON_PATH=$(poetry env info -p)/bin/python

echo ""
echo "📋 Server Configuration:"
echo "   • MCP Server: mcp_server.py"
echo "   • API Port: 8000"
echo "   • Python: $PYTHON_PATH"
echo "   • Interactive Docs: http://localhost:8000/docs"
echo ""
echo "🔧 Available Tools (will be exposed as REST endpoints):"
echo "   • POST /create_sandbox - Create isolated Python environment"
echo "   • POST /execute_python - Execute Python code in sandbox"
echo "   • GET  /list_sandboxes - List active sandboxes"
echo "   • POST /delete_sandbox - Clean up sandbox resources"
echo ""
echo "🌐 To use with Open WebUI:"
echo "   1. Open WebUI → Settings → Tools"
echo "   2. Add OpenAPI server: http://localhost:8000/openapi.json"
echo "   3. Your AI models will now have code execution capabilities!"
echo ""
echo "Starting server..."
echo ""

# Run mcpo with the MCP server
# Using poetry's python to ensure all dependencies are available
uvx mcpo --port 8000 -- "$PYTHON_PATH" /Users/oliver/code/a10-hackathon/mcp_server.py

