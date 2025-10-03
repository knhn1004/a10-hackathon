# Open WebUI Integration Guide

This guide shows you how to use the MCP Code Sandbox Server with Open WebUI through the mcpo proxy.

## 🎯 What This Does

Your MCP code sandbox server will be exposed as standard REST API endpoints that Open WebUI can use. This gives your AI models in Open WebUI the ability to:
- Execute Python code in secure Docker containers
- Generate matplotlib visualizations
- Perform data analysis with numpy/pandas
- Run calculations and complex computations

## 📋 Prerequisites

1. **Docker** running on your system
2. **Python 3.10+** with Poetry installed
3. **Open WebUI** running (either locally or cloud-hosted)
4. **uv** package runner: `pip install uv` or `brew install uv`

## 🚀 Quick Start

### Step 1: Build the Sandbox Docker Image

```bash
cd /Users/oliver/code/a10-hackathon
docker build -t code-sandbox:latest .
```

### Step 2: Run the MCP Server with mcpo Proxy

```bash
# Make the script executable
chmod +x run_mcpo.sh

# Start the server
./run_mcpo.sh
```

The server will start on `http://localhost:8000` with:
- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### Step 3: Configure Open WebUI

#### Option A: Using Open WebUI Web Interface

1. Open your Open WebUI instance
2. Go to **Settings** → **Tools** (or **Admin Panel** → **Tools**)
3. Click **"Add OpenAPI Server"** or **"+ Add Tool"**
4. Enter the OpenAPI URL:
   - If Open WebUI is running locally: `http://localhost:8000/openapi.json`
   - If Open WebUI is in Docker: `http://host.docker.internal:8000/openapi.json`
   - If Open WebUI is remote: `http://YOUR_IP:8000/openapi.json`
5. Click **"Import"** or **"Add"**

#### Option B: Using Open WebUI Configuration File

If you're running Open WebUI with environment variables or config files:

```bash
# Set the OpenAPI server URL
OPENAPI_SERVERS='[{"url": "http://localhost:8000/openapi.json", "name": "Code Sandbox"}]'
```

### Step 4: Test It!

In Open WebUI, start a conversation and try:

```
"Create a sandbox and calculate fibonacci(10)"
```

or

```
"Plot a sine wave from 0 to 2π"
```

or

```
"Calculate the mean of [1,2,3,4,5] using numpy"
```

The AI should automatically use the code sandbox tools!

## 🐳 Running mcpo in Docker (Optional)

If you want to containerize the entire mcpo proxy:

### Create Dockerfile.mcpo

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

# Install mcpo and uv
RUN pip install mcpo uv

# Copy MCP server files
COPY mcp_server.py sandbox_server.py ./

# Expose API port
EXPOSE 8000

# Run mcpo with MCP server
CMD ["uvx", "mcpo", "--host", "0.0.0.0", "--port", "8000", "--", "python", "mcp_server.py"]
```

### Build and Run

```bash
docker build -f Dockerfile.mcpo -t mcp-sandbox-api .

docker run -d \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --name mcp-sandbox-api \
  mcp-sandbox-api
```

**Note**: Mounting `/var/run/docker.sock` allows the container to create sandbox containers.

## 🔧 Troubleshooting

### "Connection Refused" in Open WebUI

If Open WebUI is running in Docker and can't reach `localhost:8000`:

1. Use `http://host.docker.internal:8000/openapi.json` instead
2. Or add `--network=host` when running Open WebUI container
3. Or run mcpo in the same Docker network as Open WebUI

### "Invalid transport" Error

This was your original error - it's unrelated to MCP setup. To fix:
1. Clear browser cache
2. Try accessing Open WebUI in incognito mode
3. Check WebSocket support in your reverse proxy (if using one)
4. Restart Open WebUI container: `docker restart open-webui`

### Tools Not Showing Up in Open WebUI

1. Check the OpenAPI endpoint is accessible: `curl http://localhost:8000/openapi.json`
2. Verify the URL in Open WebUI settings is correct
3. Refresh Open WebUI or reload the tools list
4. Check Open WebUI logs for import errors

### Sandbox Creation Fails

1. Ensure Docker is running: `docker info`
2. Check the sandbox image exists: `docker images | grep code-sandbox`
3. Rebuild if needed: `docker build -t code-sandbox:latest .`
4. Check Docker logs: `docker logs <sandbox-container-id>`

## 📊 API Endpoints

Once running, these REST endpoints are available:

- **POST** `/create_sandbox` - Create new sandbox
  ```json
  {}
  ```

- **POST** `/execute_python` - Execute Python code
  ```json
  {
    "sandbox_id": "sandbox-xxx",
    "code": "print('Hello World')"
  }
  ```

- **GET** `/list_sandboxes` - List active sandboxes
  ```json
  {}
  ```

- **POST** `/delete_sandbox` - Delete sandbox
  ```json
  {
    "sandbox_id": "sandbox-xxx"
  }
  ```

Visit http://localhost:8000/docs for interactive documentation!

## 🎓 Example Workflow

1. User in Open WebUI: "Calculate the sum of squares from 1 to 100"
2. AI calls `create_sandbox` → gets `sandbox_id`
3. AI calls `execute_python` with code:
   ```python
   result = sum(i**2 for i in range(1, 101))
   print(f"Sum of squares: {result}")
   ```
4. AI presents result to user
5. (Optional) AI calls `delete_sandbox` to clean up

## 🔗 Resources

- [Open WebUI MCP Documentation](https://docs.openwebui.com/openapi-servers/mcp)
- [mcpo GitHub Repository](https://github.com/open-webui/mcpo)
- [Model Context Protocol](https://modelcontextprotocol.io)

## 🎉 Success!

You now have a secure code execution sandbox integrated with Open WebUI! Your AI models can now:
- ✅ Execute Python code safely
- ✅ Create data visualizations
- ✅ Perform complex calculations
- ✅ Analyze data with pandas/numpy

Happy coding! 🚀

