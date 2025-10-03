#!/usr/bin/env python3
"""
Code Sandbox MCP Server

An MCP (Model Context Protocol) server that provides secure code execution
in isolated Docker containers. Inspired by CrewAI's code interpreter tool.

Exposes tools for:
- Creating sandboxes
- Executing Python code
- Managing sandbox lifecycle

Best practices implemented:
- Secure sandbox isolation via Docker
- Resource limits (CPU, memory)
- Automatic cleanup of idle sandboxes
- Comprehensive error handling
- Audit logging
"""

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import docker
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("code-sandbox-mcp")

# Configuration
IMAGE_NAME = os.getenv("SANDBOX_IMAGE", "code-sandbox:latest")
CONTAINER_PREFIX = "sandbox_"
SANDBOX_PORT = 8000
IDLE_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "300"))  # 5 minutes
MAX_SANDBOXES = int(os.getenv("MAX_SANDBOXES", "10"))
CHECK_INTERVAL = 60

# Global state
docker_client = docker.from_env()
http_client = httpx.AsyncClient(timeout=30.0)
sandboxes: Dict[str, Dict[str, Any]] = {}
sandbox_owners: Dict[str, str] = {}  # sandbox_id -> session_id


class SandboxManager:
    """Manages Docker-based code execution sandboxes."""

    @staticmethod
    async def create_sandbox(session_id: str) -> Dict[str, Any]:
        """Create a new isolated sandbox."""
        # Check sandbox limit
        user_sandboxes = [
            sid for sid, owner in sandbox_owners.items() if owner == session_id
        ]
        if len(user_sandboxes) >= MAX_SANDBOXES:
            raise ValueError(f"Maximum number of sandboxes ({MAX_SANDBOXES}) reached")

        container_name = CONTAINER_PREFIX + str(uuid.uuid4())[:8]

        logger.info(f"Creating sandbox: {container_name} for session: {session_id}")

        try:
            container = await asyncio.to_thread(
                docker_client.containers.run,
                IMAGE_NAME,
                name=container_name,
                labels={
                    "sandbox": "1",
                    "sandbox_lang": "python",
                    "session_id": session_id,
                },
                detach=True,
                ports={f"{SANDBOX_PORT}/tcp": 0},
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=50000,
                network_mode="bridge",  # Isolated network
                security_opt=["no-new-privileges"],  # Security hardening
            )

            sandbox_id = container.id[:12]
            sandboxes[sandbox_id] = {
                "id": sandbox_id,
                "name": container_name,
                "created_at": time.time(),
                "last_active": time.time(),
                "execution_count": 0,
            }
            sandbox_owners[sandbox_id] = session_id

            # Wait for container to be ready
            await asyncio.sleep(2)

            logger.info(f"Sandbox created successfully: {sandbox_id}")

            return {"sandbox_id": sandbox_id, "name": container_name, "status": "ready"}

        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            raise

    @staticmethod
    async def execute_code(
        sandbox_id: str, code: str, session_id: str
    ) -> Dict[str, Any]:
        """Execute Python code in a sandbox."""
        # Verify ownership
        if sandbox_owners.get(sandbox_id) != session_id:
            raise ValueError("Sandbox not found or access denied")

        if sandbox_id not in sandboxes:
            raise ValueError(f"Sandbox {sandbox_id} not found")

        logger.info(f"Executing code in sandbox: {sandbox_id}")

        try:
            container = await asyncio.to_thread(
                docker_client.containers.get, sandbox_id
            )

            ports = container.attrs["NetworkSettings"]["Ports"]
            port_mapping = ports.get(f"{SANDBOX_PORT}/tcp", [])

            if not port_mapping:
                raise ValueError("Sandbox not ready - no exposed port")

            host_port = port_mapping[0]["HostPort"]
            sandbox_url = f"http://localhost:{host_port}/execute"

            # Execute code
            response = await http_client.post(sandbox_url, json={"code": code})

            if not response.is_success:
                raise ValueError(f"Execution failed: {response.text}")

            # Update sandbox stats
            sandboxes[sandbox_id]["last_active"] = time.time()
            sandboxes[sandbox_id]["execution_count"] += 1

            result = response.json()
            logger.info(f"Code executed successfully in sandbox: {sandbox_id}")

            return result

        except docker.errors.NotFound:
            # Clean up stale reference
            sandboxes.pop(sandbox_id, None)
            sandbox_owners.pop(sandbox_id, None)
            raise ValueError(f"Sandbox {sandbox_id} no longer exists")
        except Exception as e:
            logger.error(f"Execution error in sandbox {sandbox_id}: {e}")
            raise

    @staticmethod
    async def list_sandboxes(session_id: str) -> list:
        """List all sandboxes owned by the session."""
        user_sandboxes = [
            sandboxes[sid]
            for sid, owner in sandbox_owners.items()
            if owner == session_id and sid in sandboxes
        ]
        return user_sandboxes

    @staticmethod
    async def delete_sandbox(sandbox_id: str, session_id: str) -> Dict[str, str]:
        """Delete a sandbox."""
        # Verify ownership
        if sandbox_owners.get(sandbox_id) != session_id:
            raise ValueError("Sandbox not found or access denied")

        logger.info(f"Deleting sandbox: {sandbox_id}")

        try:
            container = await asyncio.to_thread(
                docker_client.containers.get, sandbox_id
            )
            await asyncio.to_thread(container.stop)
            await asyncio.to_thread(container.remove)

            sandboxes.pop(sandbox_id, None)
            sandbox_owners.pop(sandbox_id, None)

            logger.info(f"Sandbox deleted: {sandbox_id}")

            return {"message": f"Sandbox {sandbox_id} deleted successfully"}

        except docker.errors.NotFound:
            # Clean up stale reference
            sandboxes.pop(sandbox_id, None)
            sandbox_owners.pop(sandbox_id, None)
            raise ValueError(f"Sandbox {sandbox_id} not found")


async def cleanup_idle_sandboxes():
    """Background task to clean up idle sandboxes."""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        now = time.time()

        for sandbox_id in list(sandboxes.keys()):
            sandbox = sandboxes[sandbox_id]
            idle_time = now - sandbox["last_active"]

            if idle_time > IDLE_TIMEOUT:
                logger.info(
                    f"Cleaning up idle sandbox: {sandbox_id} (idle: {idle_time:.0f}s)"
                )
                try:
                    container = await asyncio.to_thread(
                        docker_client.containers.get, sandbox_id
                    )
                    await asyncio.to_thread(container.stop)
                    await asyncio.to_thread(container.remove)
                except docker.errors.NotFound:
                    pass
                finally:
                    sandboxes.pop(sandbox_id, None)
                    sandbox_owners.pop(sandbox_id, None)


# Create MCP server
app = Server("code-sandbox")

# Session management (simple in-memory for demo)
current_session_id = str(uuid.uuid4())


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="create_sandbox",
            description=(
                "Create a new isolated Python code execution sandbox. "
                "Each sandbox is a Docker container with resource limits. "
                "Use this before executing any code."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="execute_python",
            description=(
                "Execute Python code in an existing sandbox. "
                "The sandbox has numpy, pandas, matplotlib, and requests available. "
                "Code execution is isolated and secure. "
                "Returns stdout, stderr, and any matplotlib plots as base64 images. "
                "You must create a sandbox first using create_sandbox."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sandbox_id": {
                        "type": "string",
                        "description": "The ID of the sandbox to execute code in",
                    },
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute",
                    },
                },
                "required": ["sandbox_id", "code"],
            },
        ),
        Tool(
            name="list_sandboxes",
            description=(
                "List all your active sandboxes with their IDs and stats. "
                "Use this to find sandbox IDs for code execution."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="delete_sandbox",
            description=(
                "Delete a sandbox and free up resources. "
                "Sandboxes are automatically deleted after 5 minutes of inactivity, "
                "but you can manually delete them sooner."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sandbox_id": {
                        "type": "string",
                        "description": "The ID of the sandbox to delete",
                    }
                },
                "required": ["sandbox_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "create_sandbox":
            result = await SandboxManager.create_sandbox(current_session_id)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Sandbox created successfully!\n\n"
                    f"Sandbox ID: {result['sandbox_id']}\n"
                    f"Status: {result['status']}\n\n"
                    f"You can now execute Python code using execute_python with this sandbox_id.",
                )
            ]

        elif name == "execute_python":
            sandbox_id = arguments.get("sandbox_id")
            code = arguments.get("code")

            if not sandbox_id or not code:
                return [
                    TextContent(
                        type="text",
                        text="❌ Error: Both sandbox_id and code are required",
                    )
                ]

            result = await SandboxManager.execute_code(
                sandbox_id, code, current_session_id
            )

            # Format results
            output_parts = []
            output_parts.append(f"📊 Execution Status: {result['status']}\n")

            for item in result.get("results", []):
                if item["type"] == "text":
                    output_parts.append(f"📝 Output:\n{item['content']}")
                elif item["type"] == "image":
                    output_parts.append(
                        f"🖼️  Generated matplotlib plot (base64 image, {len(item['content'])} chars)"
                    )
                elif item["type"] == "error":
                    output_parts.append(f"❌ Error:\n{item['content']}")
                elif item["type"] == "stderr":
                    output_parts.append(f"⚠️  Stderr:\n{item['content']}")

            return [TextContent(type="text", text="\n\n".join(output_parts))]

        elif name == "list_sandboxes":
            sandboxes_list = await SandboxManager.list_sandboxes(current_session_id)

            if not sandboxes_list:
                return [
                    TextContent(
                        type="text",
                        text="No active sandboxes. Create one with create_sandbox.",
                    )
                ]

            output_parts = [f"📋 Active Sandboxes ({len(sandboxes_list)}):\n"]
            for sb in sandboxes_list:
                age = time.time() - sb["created_at"]
                idle = time.time() - sb["last_active"]
                output_parts.append(
                    f"• {sb['id']}: {sb['name']}\n"
                    f"  Age: {age:.0f}s | Idle: {idle:.0f}s | Executions: {sb['execution_count']}"
                )

            return [TextContent(type="text", text="\n".join(output_parts))]

        elif name == "delete_sandbox":
            sandbox_id = arguments.get("sandbox_id")

            if not sandbox_id:
                return [
                    TextContent(type="text", text="❌ Error: sandbox_id is required")
                ]

            result = await SandboxManager.delete_sandbox(sandbox_id, current_session_id)
            return [TextContent(type="text", text=f"✅ {result['message']}")]

        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Tool error ({name}): {e}", exc_info=True)
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    logger.info("Starting Code Sandbox MCP Server")
    logger.info(f"Configuration:")
    logger.info(f"  Image: {IMAGE_NAME}")
    logger.info(f"  Idle Timeout: {IDLE_TIMEOUT}s")
    logger.info(f"  Max Sandboxes: {MAX_SANDBOXES}")

    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_idle_sandboxes())

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        cleanup_task.cancel()
        logger.info("MCP Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
