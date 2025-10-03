# Code Sandbox MCP Server

A **Model Context Protocol (MCP) server** that provides secure Python code execution in isolated Docker containers for LLM agents like Claude. Based on [this article](https://amirmalik.net/2025/03/07/code-sandboxes-for-llm-ai-agents).

## 🎯 What is this?

An MCP server that gives Claude (and other MCP clients) the ability to:

- Create isolated Python execution environments
- Run Python code securely in Docker containers
- Generate matplotlib visualizations
- Perform data analysis with numpy/pandas

Perfect for when you want Claude to perform calculations, data analysis, or create charts!

## 📋 Available Tools

The MCP server exposes 7 tools to Claude:

1. **`create_sandbox`** - Create a new isolated Python environment
2. **`execute_python`** - Run Python code (with numpy, pandas, matplotlib)
3. **`execute_from_url`** - Fetch code from a URL and execute it ⭐ NEW
4. **`list_sandboxes`** - See active execution environments
5. **`delete_sandbox`** - Clean up resources
6. **`inspect_container`** - Get detailed container information (Docker inspect)
7. **`get_container_metrics`** - Get real-time resource utilization metrics

## Architecture

- **MCP Server** (`mcp_server.py`): STDIO-based MCP server that orchestrates sandboxes
- **Sandbox Server** (`sandbox_server.py`): Runs inside Docker containers, executes Python code
- **Docker**: Provides isolation, resource limits, and security

```
Claude Desktop → MCP Server → Docker Containers → Code Execution
```

## Features

- ✅ **MCP Protocol** - Standard tool integration for Claude Desktop
- ✅ **Secure Isolation** - Each sandbox in separate Docker container
- ✅ **Resource Limits** - CPU (50%) and Memory (512MB) caps per sandbox
- ✅ **Auto-cleanup** - Idle sandboxes deleted after 5 minutes
- ✅ **Rich Output** - Text, matplotlib plots (base64), error tracebacks
- ✅ **Session Management** - Sandboxes owned by sessions for security
- ✅ **No Jupyter** - Direct Python `exec()` for simplicity
- ✅ **Audit Logging** - All operations logged
- ✅ **Observability** - Real-time monitoring with Docker stats/inspect
- ✅ **Web Dashboard** - Beautiful visualization of container metrics
- ✅ **Crash Handling** - Automatic crash detection with logs and recovery
- ✅ **Error Recovery** - Detailed crash reports with troubleshooting tips

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Docker** (running)
- **Poetry** for dependency management
- **Claude Desktop** (optional, for integration)

### Installation

1. **Clone and setup:**

```bash
cd /path/to/a10-hackathon
./quickstart.sh
```

Or manually:

```bash
# Install dependencies
poetry install

# Build the sandbox Docker image
docker build -t code-sandbox:latest .
```

2. **Test the MCP server:**

```bash
poetry run python test_mcp_server.py
```

3. **Integrate with Claude Desktop:**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/virtualenv/bin/python",
      "args": ["/Users/oliver/code/a10-hackathon/mcp_server.py"]
    }
  }
}
```

Find your virtualenv path:

```bash
cd /Users/oliver/code/a10-hackathon
poetry env info -p
# Use: <output>/bin/python
```

4. **Restart Claude Desktop** and you'll see the code sandbox tools! 🎉

See [MCP_README.md](MCP_README.md) for detailed integration instructions.

### Observability Dashboard

Monitor your sandboxes in real-time with the web dashboard:

```bash
./run_dashboard.sh
```

Then open **http://localhost:8080** in your browser.

The dashboard shows:

- 📊 Real-time CPU and memory usage
- 📈 Historical performance charts
- 🐳 Container status and metrics
- 🔍 Full Docker inspect data
- 📉 Resource utilization trends

See [OBSERVABILITY.md](OBSERVABILITY.md) for detailed documentation.

### Crash Handling

When containers crash (OOM, segfault, etc.), the system automatically:

```bash
# Crashes are detected in real-time
🔥 Container crash detected
   → Collects exit code, logs (stdout/stderr separated), metrics
   → Stores in crash history
   → Notifies dashboard
   → Returns detailed error to MCP caller
   → Cleans up removed containers from dashboard
```

**Features:**
- Automatic crash detection (OOM, SIGKILL, SEGFAULT)
- **Separate stdout/stderr stream collection**
- Container log capture (last 100 lines per stream)
- **Automatic dashboard cleanup of removed containers**
- Crash history API
- Troubleshooting tips in error messages
- Dashboard crash visualization

**Test crash handling:**
```bash
# Test crash detection and handling
poetry run python test_crash_handling.py

# Test stream separation and cleanup
poetry run python test_stream_separation.py
```

See [CRASH_HANDLING.md](CRASH_HANDLING.md) for detailed documentation.

### URL-Based Code Execution ⭐ NEW

Execute code directly from URLs (GitHub gists, pastebin, etc.):

```
User: "Run this gist: https://gist.githubusercontent.com/user/abc/raw/code.py"

Claude:
1. create_sandbox() → sandbox_id: xyz
2. execute_from_url(sandbox_id, url) → executes code

📥 Fetched code from: https://gist.githubusercontent.com/...
   Size: 256 bytes
   
📊 Execution Status: success
📝 Output: [results here]
```

**Features:**
- Fetch from GitHub gists, pastebin, direct URLs
- Security validation (blocks localhost, private IPs)
- Size limit: 1MB max
- Timeout: 10 seconds
- Full sandbox isolation

See [URL_EXECUTION.md](URL_EXECUTION.md) for detailed documentation.

### Using with Ollama (Local LLM)

You can also use the MCP server with local Ollama models - **100% local, no external API calls!**

```bash
# Quick start with demo script
./demo_ollama.sh

# Or run directly
poetry run python ollama_mcp_client.py --model llama3.1:latest

# Use a code-specialized model
poetry run python ollama_mcp_client.py --model codeqwen:latest
```

**Try asking the model:**
- "Create a sandbox and calculate fibonacci(10)"
- "Plot a sine wave from 0 to 2π"
- "Calculate the mean of [1,2,3,4,5] using numpy"

**Available models** (check with `ollama list`):
- `llama3.1:latest` (4.7GB) - ⭐ Best general purpose
- `codeqwen:latest` (4.2GB) - 💻 Specialized in code
- `mistral:instruct` (4.1GB) - Good instruction following
- `codellama:13b` (7.4GB) - Larger code model

## 💡 Usage Examples

### In Claude Desktop

Once integrated, you can ask Claude things like:

**Example 1: Data Analysis**

> "Create a sandbox and analyze this data: [1,2,3,4,5]. Calculate mean, median, and std deviation."

**Example 2: Visualization**

> "Plot a sine wave from 0 to 2π and show me the graph."

**Example 3: Complex Calculations**

> "Calculate compound interest on $10,000 at 7% APR for 20 years, compounded monthly. Then create a chart showing the growth."

Claude will:

1. Call `create_sandbox` to get an isolated environment
2. Call `execute_python` with the appropriate code
3. Show you the results (text output and/or charts)
4. Optionally call `delete_sandbox` to clean up

### Direct Testing

Test the MCP server locally:

```bash
# Run the test suite
poetry run python test_mcp_server.py
```

This will:

- ✅ Create a sandbox
- ✅ Execute simple Python code
- ✅ Generate a matplotlib plot
- ✅ Test error handling
- ✅ List active sandboxes
- ✅ Clean up resources

## ⚙️ Configuration

Customize behavior via environment variables in your Claude Desktop config:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/python",
      "args": ["mcp_server.py"],
      "env": {
        "SANDBOX_IMAGE": "code-sandbox:latest",
        "SANDBOX_TIMEOUT": "300",
        "MAX_SANDBOXES": "10"
      }
    }
  }
}
```

**Configuration Options:**

- ****`SANDBOX_IMAGE`**** - Docker image name (default: `code-sandbox:latest`)
- `SANDBOX_TIMEOUT` - Idle timeout in seconds (default: `300` = 5 minutes)
- `MAX_SANDBOXES` - Maximum sandboxes per session (default: `10`)

**Resource Limits** (edit `mcp_server.py`):

- Memory: 512MB per sandbox (with swap disabled)
- CPU: 50% of one core per sandbox
- PIDs: 100 processes max (prevents fork bombs)
- Network: Isolated bridge network

### Docker Logs Monitoring

All executed code output is mirrored to Docker container logs for debugging and monitoring:

```bash
# Watch logs in real-time
docker logs -f <container_id>

# View last 50 lines
docker logs --tail 50 <container_id>
```

**Log Format:**
- `[STDOUT]` prefix for standard output
- `[STDERR]` prefix for error output
- `[CODE EXECUTION START]` / `[CODE EXECUTION COMPLETE]` markers
- `[CODE EXECUTION ERROR]` with full tracebacks
- `[IMAGE]` notifications for matplotlib plot generation

**Example:**
```
============================================================
[CODE EXECUTION START]
============================================================
[STDOUT] Hello from Python!
[STDOUT] Result: 42
[STDERR] Warning: deprecation notice
============================================================
[CODE EXECUTION COMPLETE]
============================================================
```

This allows you to monitor code execution in real-time using standard Docker tools, independent of the API response.

## 🔒 Security

**Implemented:**

- ✅ Docker container isolation per sandbox
- ✅ Resource limits (CPU, memory, PIDs) enforced
- ✅ **Fork bomb protection** (PID limit: 100)
- ✅ **Crypto mining protection** (auto-kill on detection)
- ✅ Network monitoring and anomaly detection
- ✅ Network isolation (bridge mode)
- ✅ Security hardening (`no-new-privileges`)
- ✅ Session-based ownership
- ✅ Automatic cleanup of idle sandboxes
- ✅ Audit logging of all operations

### Crypto Mining Protection

Automatic detection and termination of crypto mining activity:

**Detection:**
- 🚨 **CPU Mining**: Sustained CPU > 85% for 10+ seconds → **AUTO-KILL**
- ⚠️ **Network Mining**: High CPU + network usage → Alert
- 📊 **Anomaly Detection**: Unusual resource spikes → Alert

**Example of detected mining:**
```python
import hashlib

# This code will be detected and terminated
nonce = 0
while True:
    hash_output = hashlib.sha256(f"block{nonce}".encode()).hexdigest()
    nonce += 1  # High sustained CPU = Mining detected → Container killed
```

**Monitoring:**
- Real-time metrics (CPU, memory, network)
- Historical analysis (detect anomalies)
- Alert system (critical events logged)
- Dashboard visualization

**API Endpoints:**
```bash
GET /api/alerts                      # All security alerts
GET /api/alerts/critical             # Critical alerts only
GET /api/containers/{id}/alerts      # Per-container alerts
```

See [MINING_PROTECTION.md](MINING_PROTECTION.md) for detailed documentation.

**For Production, Add:**

- [ ] gVisor or Firecracker for VM-level isolation
- [ ] Network egress filtering (block mining pools)
- [ ] Authentication & authorization
- [ ] Per-user rate limiting
- [ ] Secrets management (HashiCorp Vault)
- [ ] Storage encryption

See [MCP_README.md](MCP_README.md#-security-features) for detailed security documentation.

## 📐 Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation, design decisions, and comparison with other approaches.

## 📚 Documentation

- **[README.md](README.md)** (this file) - Quick start and overview
- **[MCP_README.md](MCP_README.md)** - Full MCP server documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Architecture deep dive
- **[OBSERVABILITY.md](OBSERVABILITY.md)** - Monitoring and dashboard guide
- **[CRASH_HANDLING.md](CRASH_HANDLING.md)** - Crash detection and recovery guide
- **[FORK_BOMB_PROTECTION.md](FORK_BOMB_PROTECTION.md)** - Fork bomb protection guide
- **[MINING_PROTECTION.md](MINING_PROTECTION.md)** - Crypto mining detection and prevention
- **[URL_EXECUTION.md](URL_EXECUTION.md)** - URL-based code execution guide
- **[DOCKER_LOGS_MIRRORING.md](DOCKER_LOGS_MIRRORING.md)** - Docker logs monitoring guide
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - File organization and metrics
- **[claude_desktop_config.example.json](claude_desktop_config.example.json)** - Example Claude config

**Source Code:**

- **[mcp_server.py](mcp_server.py)** - Main MCP server implementation
- **[sandbox_server.py](sandbox_server.py)** - In-container code execution
- **[monitor.py](monitor.py)** - Docker metrics collection
- **[dashboard_server.py](dashboard_server.py)** - Observability dashboard API
- **[dashboard.html](dashboard.html)** - Dashboard web UI
- **[test_mcp_server.py](test_mcp_server.py)** - Test suite
- **[ollama_mcp_client.py](ollama_mcp_client.py)** - Ollama local LLM client

## 🙏 Credits

Inspired by:

- [Code Sandboxes for LLMs Article](https://amirmalik.net/2025/03/07/code-sandboxes-for-llm-ai-agents) by Amir Malik
- [CrewAI Code Interpreter Tool](https://github.com/crewAIInc/crewAI-tools)
- [Model Context Protocol](https://modelcontextprotocol.io) by Anthropic

## 📄 License

MIT
