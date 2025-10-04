#!/bin/bash
# Interactive MCP Installation Script
# Prompts for all required configuration

set -e

echo "🔧 Code Sandbox MCP Server - Interactive Setup"
echo "==============================================="
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
echo "Do you want to enable API token authentication?"
echo "(This ties MCP requests to your user account for tracking)"
echo ""
read -p "Enable authentication? (y/N): " -n 1 -r
echo ""

REQUIRE_TOKEN="false"
MCP_API_TOKEN=""
DASHBOARD_URL="http://localhost:8080"

if [[ $REPLY =~ ^[Yy]$ ]]; then
    REQUIRE_TOKEN="true"
    
    echo ""
    echo "📋 To use authentication, you need:"
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
        echo "⚠️  No token provided. You can add it later to the config file."
        REQUIRE_TOKEN="false"
    elif [[ ! "$MCP_API_TOKEN" =~ ^mcp_ ]]; then
        echo "⚠️  Warning: Token should start with 'mcp_'"
    fi
else
    echo "ℹ️  Authentication disabled. MCP will run without auth."
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
echo "  Token Auth: $REQUIRE_TOKEN"
if [ "$REQUIRE_TOKEN" = "true" ] && [ -n "$MCP_API_TOKEN" ]; then
    echo "  API Token: ${MCP_API_TOKEN:0:15}...${MCP_API_TOKEN: -5}"
fi
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

# Generate config
if [ "$REQUIRE_TOKEN" = "true" ] && [ -n "$MCP_API_TOKEN" ]; then
    # With authentication
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
else
    # Without authentication
    cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "code-sandbox": {
      "command": "$PYTHON_PATH",
      "args": ["$SCRIPT_DIR/mcp_server.py"],
      "env": {
        "REQUIRE_TOKEN": "false",
        "DASHBOARD_URL": "$DASHBOARD_URL",
        "SANDBOX_IMAGE": "$SANDBOX_IMAGE",
        "SANDBOX_TIMEOUT": "$SANDBOX_TIMEOUT",
        "MAX_SANDBOXES": "$MAX_SANDBOXES"
      }
    }
  }
}
EOF
fi

echo "✅ Config written to:"
echo "   $CLAUDE_CONFIG"
echo ""

# =============================================================================
# Completion
# =============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔄 Next Steps:"
echo ""
echo "1. Restart Claude Desktop:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   - Press Cmd+Q to quit Claude"
    echo "   - Reopen Claude Desktop"
else
    echo "   - Close and reopen Claude Desktop"
fi
echo ""
echo "2. Verify MCP connection:"
echo "   - Look for 🔌 icon in bottom-right"
echo "   - Should show 'code-sandbox' connected"
echo ""
echo "3. Test it:"
echo "   Ask Claude: 'Create a sandbox and calculate fibonacci(10)'"
echo ""

if [ "$REQUIRE_TOKEN" = "true" ]; then
    echo "🔑 Token Authentication Enabled:"
    echo "   • Your requests will be tracked in the dashboard"
    echo "   • View usage in 'API Tokens' tab"
    echo "   • Token: ${MCP_API_TOKEN:0:15}...${MCP_API_TOKEN: -5}"
    echo ""
    echo "💡 To update your token:"
    echo "   Edit: $CLAUDE_CONFIG"
    echo "   Change MCP_API_TOKEN value"
    echo "   Restart Claude Desktop"
    echo ""
fi

echo "📚 Documentation:"
echo "   • README.md - Project overview"
echo "   • MCP_README.md - MCP server details"
echo "   • SETUP_AUTH.md - Authentication guide"
echo ""
echo "🎉 Happy coding!"
echo ""

