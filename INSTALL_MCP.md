# Installing Code Sandbox MCP Server in Claude Desktop

This guide works for **any user** on **any machine** (Mac/Linux/Windows).

## Prerequisites

1. Claude Desktop installed
2. Docker installed and running
3. Poetry installed (`pip install poetry`)
4. This repository cloned

## Installation Steps

### 1. Build the Docker Image

From the project directory:

```bash
cd a10-hackathon
docker build -t code-sandbox:latest .
```

### 2. Install Python Dependencies

```bash
poetry install
```

### 3. Configure Claude Desktop

#### Option A: Using the Helper Script (Mac/Linux)

```bash
# This will generate the config with correct paths
./install_mcp.sh
```

#### Option B: Manual Configuration

**Mac/Linux:**

Open Claude Desktop config:
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json  # Mac
# or
nano ~/.config/Claude/claude_desktop_config.json  # Linux
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Add this configuration** (replace `/path/to/a10-hackathon` with your actual path):

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "poetry",
      "args": [
        "run",
        "python",
        "mcp_server.py"
      ],
      "cwd": "/absolute/path/to/a10-hackathon",
      "env": {
        "SANDBOX_IMAGE": "code-sandbox:latest",
        "SANDBOX_TIMEOUT": "300",
        "MAX_SANDBOXES": "10"
      }
    }
  }
}
```

**Important:** 
- Use the **absolute path** to your a10-hackathon directory
- On Mac/Linux: Use forward slashes `/Users/you/code/a10-hackathon`
- On Windows: Use forward slashes `C:/Users/you/code/a10-hackathon` (not backslashes)

### 4. Find Your Project Path

If you're not sure of your absolute path:

**Mac/Linux:**
```bash
cd a10-hackathon
pwd
```

**Windows:**
```cmd
cd a10-hackathon
cd
```

Copy this path and use it as the `cwd` value in the config.

### 5. Restart Claude Desktop

**Mac:**
- Quit Claude Desktop (Cmd+Q)
- Reopen Claude Desktop

**Windows:**
- Close Claude Desktop
- Reopen Claude Desktop

**Linux:**
- Close Claude Desktop
- Reopen Claude Desktop

### 6. Verify Installation

In Claude Desktop:

1. Look for the 🔌 icon in the bottom right corner
2. Click it - you should see `code-sandbox ✓ Connected`
3. Test with: `"Create a sandbox"`

Expected response:
```
✅ Sandbox created successfully!

Sandbox ID: abc12345
Status: ready
```

## Troubleshooting

### Server Not Connecting

Check Claude Desktop logs:

**Mac:**
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Linux:**
```bash
tail -f ~/.config/Claude/logs/mcp*.log
```

**Windows:**
```cmd
type %APPDATA%\Claude\logs\mcp*.log
```

### Test Server Manually

From the project directory:

```bash
poetry run python mcp_server.py
```

You should see:
```
INFO: Starting Code Sandbox MCP Server
INFO:   📝 Request History: /path/to/a10-hackathon/mcp_requests.json
INFO:   📂 Working Directory: /path/to/a10-hackathon
```

Press Ctrl+C to stop.

### Common Issues

**Issue:** `poetry: command not found`

**Solution:** Install poetry:
```bash
pip install poetry
# or
curl -sSL https://install.python-poetry.org | python3 -
```

**Issue:** `docker: command not found` or `Cannot connect to Docker daemon`

**Solution:** Install and start Docker Desktop

**Issue:** `ModuleNotFoundError: No module named 'docker'`

**Solution:** Install dependencies:
```bash
poetry install
```

**Issue:** Wrong working directory in logs

**Solution:** Make sure `cwd` in config points to the **absolute path** of your a10-hackathon directory

## Configuration Options

You can customize these environment variables in the config:

```json
"env": {
  "SANDBOX_IMAGE": "code-sandbox:latest",    // Docker image to use
  "SANDBOX_TIMEOUT": "300",                   // Idle timeout in seconds (5 minutes)
  "MAX_SANDBOXES": "10"                       // Max concurrent sandboxes per user
}
```

## Monitoring and Observability

The server now includes enhanced logging:

- **Request History:** All MCP requests are logged to `mcp_requests.json`
- **Working Directory:** Shown at startup
- **Request Logging:** Each request logs its path and success/failure

View request history:
```bash
cat mcp_requests.json | jq '.'
```

## Features

Once installed, you can:

✅ **Create sandboxes** - Isolated Python execution environments  
✅ **Execute Python code** - Run code securely in containers  
✅ **Execute from URL** - Fetch and run code from GitHub gists, etc.  
✅ **Mining detection** - Automatic cryptocurrency mining protection  
✅ **LLM security filter** - Optional pre-execution code review  
✅ **Monitoring** - Real-time resource usage and crash detection  

## Next Steps

See the README.md for:
- Usage examples
- Security features
- Available tools
- Advanced configuration

## Getting Help

If you encounter issues:

1. Check the logs (paths above)
2. Test the server manually
3. Verify Docker is running
4. Ensure all dependencies are installed
5. Check the absolute path in `cwd` is correct

For more details, see:
- `README.md` - Main documentation
- `EXECUTE_FROM_URL_FIX.md` - URL execution feature
- `MINING_ERROR_CLARITY_FIX.md` - Mining detection
- `REQUEST_LOGGING_FIX.md` - Logging enhancements

