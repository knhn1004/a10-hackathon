# Code Sandbox MCP Server

A secure **Model Context Protocol (MCP)** server for executing Python code in isolated Docker containers. Designed for LLM agents and AI assistants like Claude.

## 🎯 What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io) is a standard for connecting AI assistants to external tools and data sources. This implementation exposes code execution capabilities to LLMs via MCP.

## 🔧 Tools Exposed

The code-sandbox server provides 7 tools:

### 1. `create_sandbox`
Creates a new isolated Python execution environment.
```json
{
  "name": "create_sandbox",
  "description": "Create a new isolated Python code execution sandbox",
  "parameters": {}
}
```

### 2. `execute_python`
Execute Python code in an existing sandbox.
```json
{
  "name": "execute_python",
  "description": "Execute Python code in an existing sandbox",
  "parameters": {
    "sandbox_id": "string (required)",
    "code": "string (required)"
  }
}
```

### 3. `list_sandboxes`
List all active sandboxes with stats.
```json
{
  "name": "list_sandboxes",
  "description": "List all active sandboxes",
  "parameters": {}
}
```

### 4. `delete_sandbox`
Manually delete a sandbox.
```json
{
  "name": "delete_sandbox",
  "description": "Delete a sandbox",
  "parameters": {
    "sandbox_id": "string (required)"
  }
}
```

## 🚀 Setup

### Prerequisites

1. **Docker** running
2. **Python 3.10+**
3. **Poetry** for dependency management

### Installation

```bash
# Install dependencies
poetry install

# Build the sandbox Docker image
docker build -t code-sandbox:latest .

# Test the code-sandbox server
poetry run python mcp_server.py
```

### Configuration

Set environment variables to customize behavior:

```bash
export SANDBOX_IMAGE="code-sandbox:latest"
export SANDBOX_TIMEOUT="300"  # 5 minutes
export MAX_SANDBOXES="10"     # Per session
```

## 🔌 Integration

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Option 1: Using virtualenv Python directly (Recommended)**
```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/virtualenv/bin/python",
      "args": ["/path/to/a10-hackathon/mcp_server.py"],
      "env": {
        "SANDBOX_IMAGE": "code-sandbox:latest",
        "SANDBOX_TIMEOUT": "300",
        "MAX_SANDBOXES": "10"
      }
    }
  }
}
```

To find your virtualenv path:
```bash
cd /path/to/a10-hackathon
poetry env info -p
# Use: <path>/bin/python
```

**Option 2: Using Poetry (if poetry is in PATH)**
```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "/path/to/.local/bin/poetry",
      "args": ["run", "python", "/path/to/a10-hackathon/mcp_server.py"],
      "env": {
        "SANDBOX_IMAGE": "code-sandbox:latest"
      }
    }
  }
}
```

Restart Claude Desktop to load the server.

### Other MCP Clients

Any MCP client can connect via STDIO:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
    env={
        "SANDBOX_IMAGE": "code-sandbox:latest"
    }
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # List available tools
        tools = await session.list_tools()
        
        # Call a tool
        result = await session.call_tool("create_sandbox", {})
```

## 💡 Usage Example

When integrated with Claude or another LLM:

**User:** "Calculate the compound interest on $1000 at 5% for 10 years and create a chart"

**Claude (using MCP):**
1. Calls `create_sandbox` → Gets sandbox_id
2. Calls `execute_python` with:
   ```python
   principal = 1000
   rate = 0.05
   years = 10
   amount = principal * (1 + rate) ** years
   print(f"Final amount: ${amount:.2f}")
   ```
3. Calls `execute_python` again with matplotlib code to generate chart
4. Returns results to user

## 🔒 Security Features

Based on MCP best practices ([sources](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)):

### Implemented

✅ **Docker Isolation** - Each sandbox runs in a separate container
✅ **Resource Limits** - CPU (50%) and Memory (512MB) caps per sandbox
✅ **Network Isolation** - Containers run in bridge network mode
✅ **Security Hardening** - `no-new-privileges` security option
✅ **Automatic Cleanup** - Idle sandboxes deleted after timeout
✅ **Session Isolation** - Sandboxes are owned by sessions
✅ **Audit Logging** - All operations are logged
✅ **Environment Variables** - Secrets via env vars, not hardcoded

### Recommended for Production

- [ ] **gVisor or Firecracker** - Add VM-level isolation
- [ ] **Network egress filtering** - Restrict outbound connections
- [ ] **Authentication** - Add user authentication layer
- [ ] **Rate limiting** - Per-user execution limits
- [ ] **Storage encryption** - Encrypt sandbox filesystems
- [ ] **Secrets management** - Use HashiCorp Vault or AWS Secrets Manager

## 📊 Monitoring

The server logs all operations:

```
2025-10-03 10:30:15 - code-sandbox-mcp - INFO - Creating sandbox: sandbox_abc123 for session: def456
2025-10-03 10:30:17 - code-sandbox-mcp - INFO - Sandbox created successfully: abc123
2025-10-03 10:30:20 - code-sandbox-mcp - INFO - Executing code in sandbox: abc123
2025-10-03 10:30:21 - code-sandbox-mcp - INFO - Code executed successfully in sandbox: abc123
```

## 🎨 Comparison: REST API vs MCP

This project provides **both** interfaces:

| Feature | REST API (`manager_server.py`) | MCP Server (`mcp_server.py`) |
|---------|-------------------------------|------------------------------|
| **Use Case** | Direct HTTP integration | LLM tool integration |
| **Transport** | HTTP | STDIO |
| **Authentication** | Manual (to add) | Handled by MCP client |
| **Discovery** | OpenAPI docs | MCP tool listing |
| **Best For** | Web services, APIs | Claude, AI assistants |

**When to use REST API:** Building a web service, integrating with existing APIs, need HTTP endpoints

**When to use MCP:** Integrating with Claude Desktop, building LLM agents, following MCP standard

## 🧪 Testing

Test the MCP server locally:

```bash
# Start the server (it will wait for STDIO input)
poetry run python mcp_server.py

# In another terminal, test with the MCP Inspector
npx @modelcontextprotocol/inspector poetry run python mcp_server.py
```

Or test the REST API:

```bash
# Start REST API
poetry run python manager_server.py

# Test
poetry run python example_usage.py
```

## 📚 Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [CrewAI Code Interpreter Tool](https://github.com/crewAIInc/crewAI-tools/blob/main/crewai_tools/tools/code_interpreter_tool/code_interpreter_tool.py)
- [MCP Server Best Practices](https://www.docker.com/blog/mcp-server-best-practices/)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)

## 🤝 Contributing

This is a simplified implementation for learning and development. For production use:

1. Add proper authentication
2. Implement rate limiting
3. Use gVisor or Firecracker for additional isolation
4. Add comprehensive monitoring
5. Implement secrets management
6. Add integration tests

## 📄 License
MIT

