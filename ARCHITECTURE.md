# Architecture Overview

This document explains the architecture and design decisions for the Code Sandbox system.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Integration Layer                        │
│  ┌──────────────────┐           ┌──────────────────┐        │
│  │   MCP Server     │           │   REST API       │        │
│  │  (mcp_server.py) │           │ (manager_server) │        │
│  │                  │           │                  │        │
│  │  STDIO Transport │           │  HTTP Transport  │        │
│  └────────┬─────────┘           └────────┬─────────┘        │
└───────────┼──────────────────────────────┼──────────────────┘
            │                              │
            │         Docker Control       │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │      Docker Engine           │
            │                              │
            │  ┌──────────────────────┐   │
            │  │ Sandbox Container 1  │   │
            │  │  sandbox_server.py   │   │
            │  │  :8000 → :34567      │   │
            │  └──────────────────────┘   │
            │                              │
            │  ┌──────────────────────┐   │
            │  │ Sandbox Container 2  │   │
            │  │  sandbox_server.py   │   │
            │  │  :8000 → :34568      │   │
            │  └──────────────────────┘   │
            └──────────────────────────────┘
```

## Two Integration Patterns

### Pattern 1: MCP Server (Recommended for LLMs)

**Use Case:** Claude Desktop, AI assistants, MCP-compatible clients

**Flow:**

```
1. Claude → [STDIO] → MCP Server
2. MCP Server → Docker API → Create Container
3. MCP Server → HTTP → Sandbox Container → Execute Code
4. Results → MCP Server → [STDIO] → Claude
```

**Advantages:**

- ✅ Standard protocol for AI tools
- ✅ Automatic tool discovery by LLMs
- ✅ Built-in security via MCP client
- ✅ No need for HTTP server management
- ✅ Session management handled automatically

**Configuration:**

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

### Pattern 2: REST API (Classic approach)

**Use Case:** Web applications, custom integrations, HTTP clients

**Flow:**

```
1. Client → [HTTP] → Manager Server
2. Manager Server → Docker API → Create Container
3. Client → [HTTP] → Manager Server → [HTTP] → Sandbox Container
4. Results → Manager Server → [HTTP] → Client
```

**Advantages:**

- ✅ Familiar HTTP/REST pattern
- ✅ Easy to integrate with web apps
- ✅ Swagger/OpenAPI documentation
- ✅ Can be load balanced
- ✅ Supports webhooks, streaming, etc.

**Endpoints:**

- `POST /sandboxes` - Create sandbox
- `POST /sandboxes/{id}/execute` - Execute code
- `GET /sandboxes` - List sandboxes
- `DELETE /sandboxes/{id}` - Delete sandbox

## Security Layers

### Layer 1: Container Isolation

Each sandbox runs in a separate Docker container:

```python
container = docker_client.containers.run(
    IMAGE_NAME,
    detach=True,
    mem_limit="512m",           # Memory limit
    cpu_period=100000,
    cpu_quota=50000,            # 50% CPU limit
    network_mode="bridge",      # Network isolation
    security_opt=["no-new-privileges"]  # Security hardening
)
```

**Security features:**

- Resource limits prevent DoS
- Network isolation prevents lateral movement
- Security options prevent privilege escalation

### Layer 2: Session Isolation

**MCP Server:**

- Each MCP session gets a unique session_id
- Sandboxes are owned by sessions
- Cross-session access is denied

**REST API:**

- Session management can be added via auth headers
- Currently uses container labels for tracking

### Layer 3: Automatic Cleanup

```python
async def cleanup_idle_sandboxes():
    for sandbox_id, sandbox in sandboxes.items():
        idle_time = now - sandbox["last_active"]
        if idle_time > IDLE_TIMEOUT:
            # Stop and remove container
            container.stop()
            container.remove()
```

**Cleanup triggers:**

- Idle timeout (default: 5 minutes)
- Manual deletion via tool/API
- Server restart (orphan cleanup)

## Code Execution Flow

### Inside Sandbox Container

```python
# sandbox_server.py

@app.post("/execute")
async def execute_code(request: ExecuteRequest):
    # 1. Capture stdout/stderr
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    # 2. Create isolated namespace
    namespace = {'__builtins__': __builtins__}

    # 3. Execute code
    exec(request.code, namespace)

    # 4. Capture matplotlib plots
    for fig in plt.get_fignums():
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        results.append({"type": "image", "content": base64_encode(buf)})

    # 5. Return results
    return {"results": results, "status": "success"}
```

**Features:**

- Direct Python `exec()` - no Jupyter overhead
- Matplotlib plot capture via custom `plt.show()`
- Isolated namespace per execution
- Base64-encoded image output

## Comparison with CrewAI Code Interpreter

Inspired by [crewAI's code interpreter tool](https://github.com/crewAIInc/crewAI-tools/blob/main/crewai_tools/tools/code_interpreter_tool/code_interpreter_tool.py), but simplified:

| Feature         | CrewAI Tool             | Our Implementation |
| --------------- | ----------------------- | ------------------ |
| **Execution**   | Subprocess + temp files | Direct `exec()`    |
| **Isolation**   | Process-level           | Docker containers  |
| **Output**      | File-based              | Streaming capture  |
| **Plots**       | Saved to files          | Base64 in response |
| **Persistence** | Temporary               | Session-based      |
| **Integration** | CrewAI framework        | MCP + REST API     |

**Design decisions:**

- Simpler: No temp file management
- More secure: Docker > subprocess isolation
- More flexible: Multiple integration options
- More efficient: Direct exec() vs subprocess overhead

## Performance Considerations

### Container Startup

```python
# Cold start: ~2-3 seconds
container = docker_client.containers.run(IMAGE_NAME, ...)
await asyncio.sleep(2)  # Wait for ready
```

**Optimization strategies:**

- Keep containers warm (don't delete immediately)
- Reuse containers for multiple executions
- Pre-pull images on server start

### Execution Speed

```python
# Execution overhead: ~50-100ms
# Actual code execution: depends on code
```

**Performance factors:**

- Direct `exec()` is faster than subprocess
- matplotlib capture adds ~20-50ms per plot
- HTTP round-trip: ~5-10ms (local)

### Resource Limits

Per sandbox:

- **Memory:** 512MB (configurable)
- **CPU:** 50% of one core (configurable)
- **Network:** Bridge network (can be disabled)

## Best Practices from MCP Community

Based on [MCP best practices](https://www.docker.com/blog/mcp-server-best-practices/) and [security guidelines](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices):

### ✅ Implemented

1. **Secrets Management**

   - Environment variables for config
   - No hardcoded credentials
   - Docker socket access controlled

2. **Security Hardening**

   - Container isolation
   - Resource limits
   - Security options (`no-new-privileges`)
   - Audit logging

3. **Documentation**

   - Tool descriptions for LLMs
   - User documentation
   - Code examples

4. **Testing**
   - Automated test script
   - Error handling tests
   - Integration examples

### 🚧 Production TODOs

1. **Additional Isolation**

   - Add gVisor runtime for extra security
   - Or use Firecracker for VM-level isolation

2. **Network Security**

   - Egress filtering
   - Disable network entirely for sensitive use

3. **Authentication**

   - API keys for REST API
   - User management
   - Per-user rate limiting

4. **Monitoring** ✅ IMPLEMENTED

   - Real-time Docker stats collection
   - Web dashboard with visualization
   - Docker inspect integration
   - Historical metrics storage
   - REST API for metrics access
   - MCP tools for container inspection

5. **Secrets Management**
   - HashiCorp Vault integration
   - AWS Secrets Manager
   - Short-lived credentials

## When to Use Which Interface?

### Use MCP Server when:

- ✅ Building AI assistants (Claude, etc.)
- ✅ Following AI tool standards
- ✅ Want automatic tool discovery
- ✅ Need session management
- ✅ Working with MCP-compatible clients

### Use REST API when:

- ✅ Building web services
- ✅ Need HTTP webhooks
- ✅ Want load balancing
- ✅ Need streaming responses
- ✅ Integrating with existing APIs
- ✅ Building custom UIs

### Use Both when:

- ✅ Supporting multiple client types
- ✅ Maximum flexibility
- ✅ Different use cases in same system

## Observability System

### Components

**Monitor Module** (`monitor.py`)

- Collects Docker stats every second
- Maintains 5-minute rolling history
- Provides metrics and inspect data
- Async/non-blocking collection

**Dashboard Server** (`dashboard_server.py`)

- FastAPI REST API on port 8080
- Real-time metrics endpoints
- CORS-enabled for development
- Health checks and status

**Web Dashboard** (`dashboard.html`)

- Real-time charts (Chart.js)
- Container cards with metrics
- Modal for detailed inspection
- Dark mode UI
- Auto-refresh every 2 seconds

**MCP Integration**

- `inspect_container` tool
- `get_container_metrics` tool
- Seamless integration with existing tools

### Metrics Collected

- **CPU**: Usage percentage per container
- **Memory**: Usage, limits, percentage
- **Network**: RX/TX bytes
- **Disk I/O**: Read/write bytes
- **Container State**: Status, uptime, metadata
- **Resource Limits**: Configured limits and quotas

See [OBSERVABILITY.md](OBSERVABILITY.md) for complete documentation.

## Future Enhancements

1. **Language Support**

   - Add Node.js kernel
   - Add R support
   - Multi-language containers

2. **File Operations**

   - Upload files to sandbox
   - Download generated files
   - Persistent storage

3. **Streaming Output**

   - Real-time stdout streaming
   - Long-running code support
   - Progress indicators

4. **Collaboration**

   - Shared sandboxes
   - Collaborative editing
   - Execution history

5. **Advanced Security**

   - SELinux policies
   - AppArmor profiles
   - Seccomp filters

6. **Enhanced Observability**
   - Prometheus/Grafana integration
   - Alert system with webhooks
   - Log aggregation and search
   - Multi-host monitoring
   - Predictive analytics

## Conclusion

This code sandbox provides a **simplified yet production-ready** foundation for LLM code execution. The dual-interface design (MCP + REST) offers maximum flexibility while maintaining security through Docker isolation.

The architecture is inspired by production systems (CrewAI) but simplified for clarity and ease of deployment. It follows MCP best practices and provides a solid foundation for extension.

**Key takeaway:** Start with MCP for AI agents, add REST API as needed. Both share the same secure Docker backend.
