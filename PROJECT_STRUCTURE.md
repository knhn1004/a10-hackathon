# Project Structure

Clean, minimal MCP server implementation for code execution.

## 📁 Files

```
a10-hackathon/
├── README.md                              # Main documentation
├── MCP_README.md                          # MCP-specific docs
├── ARCHITECTURE.md                        # Architecture deep dive
├── PROJECT_STRUCTURE.md                   # This file
│
├── mcp_server.py                          # Main MCP server (STDIO)
├── sandbox_server.py                      # In-container execution API
├── test_mcp_server.py                     # Test suite
│
├── Dockerfile                             # Sandbox container image
├── claude_desktop_config.example.json     # Example config
├── quickstart.sh                          # Setup script
│
├── pyproject.toml                         # Poetry dependencies
├── poetry.lock                            # Locked dependencies
└── .gitignore                             # Git ignore rules
```

## 🎯 Core Components

### MCP Server (`mcp_server.py`)
- **Lines:** 418
- **Purpose:** Main MCP server with STDIO transport
- **Exposes:** 4 tools (create_sandbox, execute_python, list_sandboxes, delete_sandbox)
- **Manages:** Docker containers, session ownership, cleanup

### Sandbox Server (`sandbox_server.py`)
- **Lines:** 131
- **Purpose:** Runs inside Docker containers
- **Function:** Executes Python code via `exec()`
- **Returns:** Text output, matplotlib plots (base64), errors

### Test Suite (`test_mcp_server.py`)
- **Lines:** ~137
- **Tests:** All 4 MCP tools
- **Coverage:** Create, execute, list, delete, error handling

## 📝 Documentation

### README.md
- Quick start guide
- Claude Desktop integration
- Usage examples
- Configuration

### MCP_README.md
- Full MCP documentation
- Security best practices
- Integration patterns
- Tool descriptions

### ARCHITECTURE.md
- System design
- Security layers
- Performance considerations
- Comparison with alternatives

## 🔧 Configuration Files

### pyproject.toml
```toml
[tool.poetry.dependencies]
python = "^3.10"
mcp = "^1.0.0"
docker = "^7.0.0"
httpx = "^0.27.0"
fastapi = "^0.109.0"
# ... data science libs
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
# Installs: fastapi, matplotlib, numpy, pandas, requests
CMD ["python", "sandbox_server.py"]
```

### claude_desktop_config.example.json
Example configuration for Claude Desktop integration.

## 🚀 Workflow

```
1. User asks Claude to run code
   ↓
2. Claude calls create_sandbox (MCP tool)
   ↓
3. mcp_server.py creates Docker container
   ↓
4. Claude calls execute_python (MCP tool)
   ↓
5. mcp_server.py → HTTP → sandbox_server.py → exec()
   ↓
6. Results returned to Claude
   ↓
7. Auto-cleanup after 5 minutes idle
```

## 📦 Dependencies

**Runtime:**
- `mcp` - Model Context Protocol SDK
- `docker` - Docker API client
- `httpx` - Async HTTP client
- `fastapi` - API framework (in containers)
- `uvicorn` - ASGI server (in containers)
- `matplotlib`, `numpy`, `pandas` - Data science

**Dev:**
- `pytest` - Testing
- `poetry` - Dependency management

## 🔒 Security Model

1. **Container Isolation** - Docker containers per sandbox
2. **Resource Limits** - CPU (50%), Memory (512MB)
3. **Network Isolation** - Bridge network
4. **Session Ownership** - Sandboxes owned by MCP sessions
5. **Auto-cleanup** - 5-minute idle timeout
6. **Audit Logging** - All operations logged

## 📊 Metrics

- **Total Files:** 11
- **Total Lines (code):** ~700
- **Languages:** Python 100%
- **Docker Images:** 1 (code-sandbox:latest)
- **External Services:** Docker Engine
- **MCP Tools:** 4

## 🎯 Design Goals

✅ **Simplicity** - No Jupyter, direct exec()  
✅ **Security** - Docker isolation + resource limits  
✅ **Standard** - MCP protocol for AI tools  
✅ **Minimal** - No unnecessary dependencies  
✅ **Documented** - Extensive docs and examples  

## 🚫 What's NOT Included

- ❌ REST API server
- ❌ Web UI
- ❌ Database
- ❌ Authentication (uses MCP client auth)
- ❌ Multi-language support (Python only)
- ❌ File upload/download
- ❌ Persistent storage

These can be added as extensions but are not in the core implementation.

## 📈 Future Extensions

Potential additions (not implemented):
- [ ] Node.js/TypeScript support
- [ ] File upload/download
- [ ] Persistent volumes
- [ ] gVisor/Firecracker isolation
- [ ] Network egress filtering
- [ ] Streaming output
- [ ] Collaborative sandboxes
- [ ] Execution history/replay

## 🔗 External Resources

- [Model Context Protocol](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)

## 📝 Notes

- Built during A10 Hackathon
- Focused on Claude Desktop integration
- Production-ready with caveats (see security docs)
- Inspired by CrewAI code interpreter
- Follows MCP best practices

Last updated: 2025-10-03

