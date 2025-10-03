#!/bin/bash
# Quickstart script for Code Sandbox MCP Server

set -e

echo "🚀 Code Sandbox MCP Server - Quickstart"
echo "========================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "   Please start Docker and try again"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Error: Poetry is not installed"
    echo "   Install it with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo "✅ Poetry is installed"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
poetry install --no-interaction
echo ""

# Build Docker image
echo "🐳 Building sandbox Docker image..."
docker build -t code-sandbox:latest .
echo ""

echo "✅ Setup complete!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Test the MCP server:"
echo "   poetry run python test_mcp_server.py"
echo ""
echo "2. Get your virtualenv path for Claude Desktop:"
echo "   poetry env info -p"
echo "   # Use: <output>/bin/python"
echo ""
echo "3. Add to Claude Desktop config:"
echo "   File: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo "   {"
echo "     \"mcpServers\": {"
echo "       \"code-sandbox\": {"
echo "         \"command\": \"<virtualenv-path>/bin/python\","
echo "         \"args\": [\"$(pwd)/mcp_server.py\"]"
echo "       }"
echo "     }"
echo "   }"
echo ""
echo "4. Restart Claude Desktop"
echo ""
echo "📚 Documentation:"
echo "   README.md - Quick start guide"
echo "   MCP_README.md - Full MCP documentation"
echo ""

