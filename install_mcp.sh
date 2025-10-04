#!/bin/bash
# MCP Installation Script
# Always requires authentication

set -e

echo "🔧 Code Sandbox MCP Server - Setup"
echo "==================================="
echo ""

# Get absolute path to this directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Get poetry virtualenv path
VENV_PATH=$(poetry env info -p 2>/dev/null || echo "")
if [ -z "$VENV_PATH" ]; then
    echo "⚠️  Poetry virtualenv not found. Running poetry install..."
    poetry install
    VENV_PATH=$(poetry env info -p)
fi

PYTHON_PATH="$VENV_PATH/bin/python"
echo "✅ Python: $PYTHON_PATH"
echo "✅ Project: $SCRIPT_DIR"
echo ""

# Claude Desktop config location
if [[ "$OSTYPE" == "darwin"* ]]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# =============================================================================
# Configuration Prompts
# =============================================================================

echo "🔐 Authentication Configuration"
echo "================================"
echo ""
echo "This MCP server requires authentication."
echo ""
echo "📋 You need:"
echo "  1. A running dashboard (local or deployed)"
echo "  2. An API token (generate from dashboard after login)"
echo ""

read -p "Dashboard URL [http://localhost:8080]: " INPUT_URL
DASHBOARD_URL=${INPUT_URL:-http://localhost:8080}

echo ""
echo "📝 Generate your API token:"
echo "  1. Visit: $DASHBOARD_URL"
echo "  2. Login with GitHub"
echo "  3. Go to 'API Tokens' tab"
echo "  4. Click 'Generate New Token'"
echo "  5. Copy the token (starts with 'mcp_')"
echo ""

read -p "Enter your API token: " MCP_API_TOKEN

if [[ -z "$MCP_API_TOKEN" ]]; then
    echo "❌ Token is required for MCP server"
    exit 1
elif [[ ! "$MCP_API_TOKEN" =~ ^mcp_ ]]; then
    echo "⚠️  Warning: Token should start with 'mcp_'"
fi

echo ""
echo "📦 Sandbox Configuration"
echo "========================"
echo ""

read -p "Docker image [code-sandbox:latest]: " INPUT_IMAGE
SANDBOX_IMAGE=${INPUT_IMAGE:-code-sandbox:latest}

read -p "Idle timeout (seconds) [300]: " INPUT_TIMEOUT
SANDBOX_TIMEOUT=${INPUT_TIMEOUT:-300}

read -p "Max concurrent sandboxes [10]: " INPUT_MAX
MAX_SANDBOXES=${INPUT_MAX:-10}

echo ""
echo "📋 Configuration Summary:"
echo "========================="
echo "  Dashboard URL: $DASHBOARD_URL"
echo "  API Token: ${MCP_API_TOKEN:0:15}...${MCP_API_TOKEN: -5}"
echo "  Docker Image: $SANDBOX_IMAGE"
echo "  Timeout: ${SANDBOX_TIMEOUT}s"
echo "  Max Sandboxes: $MAX_SANDBOXES"
echo ""

read -p "Install with this configuration? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "❌ Installation cancelled"
    exit 0
fi

# =============================================================================
# Create Claude Desktop Config
# =============================================================================

echo ""
echo "📝 Installing to Claude Desktop..."
echo ""

# Create config directory
mkdir -p "$(dirname "$CLAUDE_CONFIG")"

# Backup existing config
if [ -f "$CLAUDE_CONFIG" ]; then
    BACKUP="$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$CLAUDE_CONFIG" "$BACKUP"
    echo "✅ Backed up existing config to:"
    echo "   $BACKUP"
    echo ""
fi

# Generate config with authentication (always required)
cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "code-sandbox": {
      "command": "$PYTHON_PATH",
      "args": ["$SCRIPT_DIR/mcp_server.py"],
      "env": {
        "MCP_API_TOKEN": "$MCP_API_TOKEN",
        "REQUIRE_TOKEN": "true",
        "DASHBOARD_URL": "$DASHBOARD_URL",
        "SANDBOX_IMAGE": "$SANDBOX_IMAGE",
        "SANDBOX_TIMEOUT": "$SANDBOX_TIMEOUT",
        "MAX_SANDBOXES": "$MAX_SANDBOXES"
      }
    }
  }
}
EOF

echo "✅ Config written to:"
echo "   $CLAUDE_CONFIG"
echo ""

# =============================================================================
# Restart Claude Desktop
# =============================================================================

echo "🔄 Restarting Claude Desktop..."
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    pkill -x "Claude" 2>/dev/null && echo "   ✅ Closed Claude Desktop" || echo "   ℹ️  Claude Desktop not running"
    sleep 2
    open -a "Claude" 2>/dev/null && echo "   ✅ Restarted Claude Desktop" || echo "   ⚠️  Could not auto-restart Claude - please open manually"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    pkill -i claude 2>/dev/null && echo "   ✅ Closed Claude Desktop" || echo "   ℹ️  Claude Desktop not running"
    sleep 2
    # Try common Linux launch methods
    if command -v claude &> /dev/null; then
        claude &> /dev/null &
        echo "   ✅ Restarted Claude Desktop"
    else
        echo "   ⚠️  Could not auto-restart Claude - please open manually"
    fi
else
    echo "   ⚠️  Auto-restart not supported on this OS - please restart Claude manually"
fi

echo ""

# =============================================================================
# Completion
# =============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔍 Verify MCP Connection:"
echo "   - Look for 🔌 icon in bottom-right of Claude"
echo "   - Should show 'code-sandbox' connected"
echo ""
echo "🧪 Test it:"
echo "   Ask Claude: 'Create a sandbox and calculate fibonacci(10)'"
echo ""
echo "🔑 Authentication:"
echo "   • Your requests are tracked in the dashboard"
echo "   • View usage in 'API Tokens' tab at $DASHBOARD_URL"
echo "   • Token: ${MCP_API_TOKEN:0:15}...${MCP_API_TOKEN: -5}"
echo ""
echo "💡 To update your token:"
echo "   Edit: $CLAUDE_CONFIG"
echo "   Change MCP_API_TOKEN value"
echo "   Restart Claude Desktop"
echo ""
echo "📚 Documentation:"
echo "   • README.md - Project overview"
echo "   • MCP_README.md - MCP server details"
echo ""
echo "🎉 Happy coding!"
echo ""
