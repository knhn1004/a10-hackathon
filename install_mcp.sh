#!/bin/bash
# Universal MCP Server Installation Script
# Works for any user on Mac/Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect the project directory (where this script is located)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    echo "This script supports Mac and Linux only."
    exit 1
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Code Sandbox MCP Server - Installation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${GREEN}✓${NC} Detected OS: $OS"
echo -e "${GREEN}✓${NC} Project directory: $PROJECT_DIR"
echo

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
echo

# Check Poetry
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}❌ Poetry not found${NC}"
    echo "Install it with: pip install poetry"
    echo "Or visit: https://python-poetry.org/docs/#installation"
    exit 1
fi
# Get absolute path to poetry and resolve any symlinks/relative paths
POETRY_PATH="$(command -v poetry)"
# Resolve to real path (remove .. and symlinks)
POETRY_PATH="$(cd "$(dirname "$POETRY_PATH")" && pwd)/$(basename "$POETRY_PATH")"
echo -e "${GREEN}✓${NC} Poetry installed at: $POETRY_PATH"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    echo "Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker installed"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker daemon not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is running"

echo

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
cd "$PROJECT_DIR"
poetry install --no-root 2>&1 | grep -v "^$" | tail -3 || true
echo -e "${GREEN}✓${NC} Dependencies installed"
echo

# Check if Docker image exists, build if not
echo -e "${BLUE}Checking Docker image...${NC}"
if ! docker images | grep -q "code-sandbox"; then
    echo "Building Docker image (this may take a few minutes)..."
    docker build -t code-sandbox:latest "$PROJECT_DIR" 2>&1 | tail -5
    echo -e "${GREEN}✓${NC} Docker image built"
else
    echo -e "${GREEN}✓${NC} Docker image exists"
fi
echo

# Generate Claude Desktop config
echo -e "${BLUE}Generating Claude Desktop configuration...${NC}"

# Create config directory if it doesn't exist
CLAUDE_CONFIG_DIR="$(dirname "$CLAUDE_CONFIG")"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Create backup if config exists
if [ -f "$CLAUDE_CONFIG" ]; then
    BACKUP="$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}Creating backup...${NC}"
    cp "$CLAUDE_CONFIG" "$BACKUP"
    echo -e "${GREEN}✓${NC} Backup saved to:"
    echo "  $BACKUP"
    echo
fi

# Generate the config with absolute poetry path and relative script path
cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "code-sandbox": {
      "command": "$POETRY_PATH",
      "args": [
        "-C",
        "$PROJECT_DIR",
        "run",
        "python",
        "$PROJECT_DIR/mcp_server.py"
      ],
      "cwd": "$PROJECT_DIR",
      "env": {
        "SANDBOX_IMAGE": "code-sandbox:latest",
        "SANDBOX_TIMEOUT": "300",
        "MAX_SANDBOXES": "10"
      }
    }
  }
}
EOF

echo -e "${GREEN}✓${NC} Configuration written to:"
echo "  $CLAUDE_CONFIG"
echo
echo "  Using:"
echo "  • Poetry: $POETRY_PATH"
echo "  • Project: $PROJECT_DIR"
echo

# Restart Claude Desktop
echo -e "${BLUE}Restarting Claude Desktop...${NC}"
echo

if [[ "$OS" == "mac" ]]; then
    # Check if Claude is running
    if pgrep -x "Claude" > /dev/null; then
        echo "Quitting Claude Desktop..."
        osascript -e 'quit app "Claude"' 2>/dev/null || true
        sleep 2
        echo -e "${GREEN}✓${NC} Claude quit"
    fi
    
    echo "Starting Claude Desktop..."
    open -a Claude 2>/dev/null && {
        echo -e "${GREEN}✓${NC} Claude Desktop started"
    } || {
        echo -e "${YELLOW}⚠️  Could not auto-start Claude Desktop${NC}"
        echo "Please open Claude Desktop manually"
    }
elif [[ "$OS" == "linux" ]]; then
    echo -e "${YELLOW}Please restart Claude Desktop manually${NC}"
fi

echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Installation Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Wait for Claude Desktop to fully start (5-10 seconds)"
echo "  2. Look for the 🔌 icon in the bottom right corner"
echo "  3. Click it to verify 'code-sandbox' is connected"
echo "  4. Test with: ${GREEN}'Create a sandbox'${NC}"
echo
echo -e "${BLUE}Expected response:${NC}"
echo "  ✅ Sandbox created successfully!"
echo "  Sandbox ID: abc12345"
echo "  Status: ready"
echo
echo -e "${BLUE}View logs:${NC}"
if [[ "$OS" == "mac" ]]; then
    echo "  tail -f ~/Library/Logs/Claude/mcp*.log"
elif [[ "$OS" == "linux" ]]; then
    echo "  tail -f ~/.config/Claude/logs/mcp*.log"
fi
echo
echo -e "${BLUE}Configuration file:${NC}"
echo "  $CLAUDE_CONFIG"
echo
echo -e "${BLUE}Project directory:${NC}"
echo "  $PROJECT_DIR"
echo

