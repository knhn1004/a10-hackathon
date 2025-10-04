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
from urllib.parse import urlparse

import docker
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging FIRST before using logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("code-sandbox-mcp")

# Optional: Import monitoring if available
try:
    from monitor import get_monitor

    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False
    logger.warning("Monitoring module not available - monitoring tools disabled")

# Optional: Import code safety filter
try:
    from code_safety_filter import get_filter as get_code_filter

    CODE_FILTER_ENABLED = True
except ImportError:
    CODE_FILTER_ENABLED = False
    logger.warning(
        "Code safety filter not available - LLM pre-execution review disabled"
    )

# Configuration
IMAGE_NAME = os.getenv("SANDBOX_IMAGE", "code-sandbox:latest")
CONTAINER_PREFIX = "sandbox_"
SANDBOX_PORT = 8000
IDLE_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "300"))  # 5 minutes
MAX_SANDBOXES = int(os.getenv("MAX_SANDBOXES", "10"))
CHECK_INTERVAL = 60

# URL fetching configuration
MAX_CODE_SIZE = 1024 * 1024  # 1MB max code size
URL_FETCH_TIMEOUT = 10.0  # 10 second timeout for fetching URLs
ALLOWED_URL_SCHEMES = ["http", "https"]
ALLOWED_CONTENT_TYPES = [
    "text/plain",
    "text/x-python",
    "application/x-python-code",
    "application/octet-stream",
]

# Global state
docker_client = docker.from_env()
http_client = httpx.AsyncClient(timeout=30.0)
sandboxes: Dict[str, Dict[str, Any]] = {}
sandbox_owners: Dict[str, str] = {}  # sandbox_id -> session_id
request_history: list = []  # Store recent MCP requests
MAX_HISTORY_SIZE = 100  # Keep last 100 requests
# Resolve paths relative to this file to avoid CWD mismatches across processes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(
    BASE_DIR, "mcp_requests.json"
)  # Shared file for cross-process access
LLM_REVIEW_FILE = os.path.join(BASE_DIR, "llm_reviews.json")

llm_review_history: list = []  # Store recent LLM code reviews


# Load existing history on startup
def load_existing_history():
    """Load existing request history from file on startup."""
    import json

    global request_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                request_history = json.load(f)
                logger.info(
                    f"📊 Loaded {len(request_history)} existing MCP requests from history"
                )
        # Load LLM reviews history if present
        if os.path.exists(LLM_REVIEW_FILE):
            with open(LLM_REVIEW_FILE, "r") as f:
                _reviews = json.load(f)
                if isinstance(_reviews, list):
                    # Keep only last MAX_HISTORY_SIZE
                    globals()["llm_review_history"] = _reviews[-MAX_HISTORY_SIZE:]
                    logger.info(
                        f"🛡️ Loaded {len(llm_review_history)} existing LLM reviews from history"
                    )
    except Exception as e:
        logger.warning(f"Could not load existing history: {e}")
        request_history = []


# Load history immediately
load_existing_history()


def log_request(tool_name: str, arguments: Dict, result: str, status: str = "success"):
    """Log MCP request to history (both in-memory and file)."""
    import json
    from datetime import datetime

    request_entry = {
        "timestamp": time.time(),
        "datetime": datetime.now().isoformat(),  # Human-readable timestamp
        "tool": tool_name,
        "arguments": arguments,
        "status": status,
        "result_preview": result[:200] if len(result) > 200 else result,
        "session_id": current_session_id,
    }

    # Keep only last MAX_HISTORY_SIZE requests in memory
    request_history.append(request_entry)
    if len(request_history) > MAX_HISTORY_SIZE:
        request_history.pop(0)

    # Also save to file for cross-process access
    try:
        # Get absolute path to ensure we know where we're writing
        history_path = os.path.abspath(HISTORY_FILE)
        logger.info(f"📝 Logging {tool_name} ({status}) to {history_path}")

        with open(history_path, "w") as f:
            json.dump(request_history, f, indent=2)

        logger.info(f"✅ Logged successfully - total history: {len(request_history)}")
    except PermissionError as e:
        logger.error(f"❌ Permission denied writing to {history_path}: {e}")
        logger.error(
            f"   Check file permissions or use a different HISTORY_FILE location"
        )
    except Exception as e:
        logger.error(f"❌ Failed to save request history to file: {e}")
        logger.error(f"   File path: {os.path.abspath(HISTORY_FILE)}")
        logger.error(f"   Current directory: {os.getcwd()}")


def log_llm_review(
    sandbox_id: str,
    code_length: int,
    review: Any,
    source: str = "execute_code",
):
    """Persist LLM code review details for dashboard visualization."""
    import json
    from datetime import datetime

    try:
        # Normalize review to dict (handle both objects and dicts)
        if isinstance(review, dict):
            review_dict = {
                "decision": review.get("decision", None),
                "confidence": review.get("confidence", None),
                "reasons": review.get("reasons", None),
                "threats_detected": review.get("threats_detected", None),
                "safe_alternative": review.get("safe_alternative", None),
            }
        else:
            review_dict = {
                "decision": getattr(review, "decision", None),
                "confidence": getattr(review, "confidence", None),
                "reasons": getattr(review, "reasons", None),
                "threats_detected": getattr(review, "threats_detected", None),
                "safe_alternative": getattr(review, "safe_alternative", None),
            }

        entry = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "sandbox_id": sandbox_id,
            "code_length": code_length,
            "session_id": current_session_id,
            "source": source,
            "review": review_dict,
        }

        llm_review_history.append(entry)
        if len(llm_review_history) > MAX_HISTORY_SIZE:
            llm_review_history.pop(0)

        with open(LLM_REVIEW_FILE, "w") as f:
            json.dump(llm_review_history, f, indent=2)
    except Exception as e:
        logger.debug(f"Failed to log LLM review: {e}")


def get_request_history(limit: int = 50) -> list:
    """Get recent request history."""
    # Try to load from file first (for cross-process access)
    import json

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                return list(reversed(history[-limit:]))
    except Exception as e:
        logger.debug(f"Failed to load request history from file: {e}")

    # Fallback to in-memory
    return list(reversed(request_history[-limit:]))


class SandboxManager:
    """Manages Docker-based code execution sandboxes."""

    @staticmethod
    async def fetch_code_from_url(url: str) -> Dict[str, Any]:
        """
        Fetch code from a URL with security checks.

        Args:
            url: URL to fetch code from

        Returns:
            Dict with code content and metadata

        Raises:
            ValueError: If URL is invalid or fetch fails
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ALLOWED_URL_SCHEMES:
                raise ValueError(
                    f"Invalid URL scheme: {parsed.scheme}. "
                    f"Allowed: {', '.join(ALLOWED_URL_SCHEMES)}"
                )

            # Block localhost and private IPs for security
            if parsed.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
                raise ValueError("Cannot fetch from localhost URLs")

            # Block private IP ranges (basic check)
            if parsed.hostname and (
                parsed.hostname.startswith("192.168.")
                or parsed.hostname.startswith("10.")
                or parsed.hostname.startswith("172.16.")
            ):
                raise ValueError("Cannot fetch from private IP addresses")

        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")

        logger.info(f"Fetching code from URL: {url}")

        try:
            # Fetch with timeout
            async with httpx.AsyncClient(timeout=URL_FETCH_TIMEOUT) as client:
                response = await client.get(url, follow_redirects=True)

                if response.status_code != 200:
                    raise ValueError(
                        f"Failed to fetch URL: HTTP {response.status_code}"
                    )

                # Check content type
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip()
                )
                if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                    logger.warning(
                        f"Unexpected content-type: {content_type}, proceeding anyway"
                    )

                # Check size
                content = response.text
                if len(content) > MAX_CODE_SIZE:
                    raise ValueError(
                        f"Code size exceeds limit: {len(content)} bytes "
                        f"(max: {MAX_CODE_SIZE})"
                    )

                if not content.strip():
                    raise ValueError("URL returned empty content")

                logger.info(f"Successfully fetched {len(content)} bytes from {url}")

                return {
                    "code": content,
                    "url": url,
                    "size": len(content),
                    "content_type": content_type,
                }

        except httpx.TimeoutException:
            raise ValueError(f"Timeout fetching URL (>{URL_FETCH_TIMEOUT}s)")
        except httpx.RequestError as e:
            raise ValueError(f"Network error fetching URL: {e}")
        except Exception as e:
            raise ValueError(f"Error fetching URL: {e}")

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
                memswap_limit="512m",  # Disable swap
                cpu_period=100000,
                cpu_quota=50000,
                # pids_limit disabled to reduce false positives on forking workloads
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

        # SECURITY: LLM-based code review before execution
        if CODE_FILTER_ENABLED:
            code_filter = get_code_filter()
            if code_filter:
                try:
                    logger.info("🛡️ Running LLM security review before execution...")
                    logger.info(f"   Container: {sandbox_id}")
                    logger.info(f"   Code length: {len(code)} bytes")

                    # Run LLM review with timeout to prevent hanging
                    review_result = await asyncio.wait_for(
                        asyncio.to_thread(code_filter.review_code, code),
                        timeout=30.0,  # 30 second timeout
                    )

                    # Log detailed results
                    logger.info(f"🤖 LLM Review Result:")
                    logger.info(f"   Decision: {review_result.decision.upper()}")
                    logger.info(f"   Confidence: {review_result.confidence:.1%}")
                    if review_result.threats_detected:
                        logger.info(
                            f"   Threats: {', '.join(review_result.threats_detected)}"
                        )
                    if review_result.reasons:
                        logger.info(
                            f"   Reasons: {'; '.join(review_result.reasons[:2])}"
                        )  # First 2 reasons

                    # Persist LLM review
                    log_llm_review(
                        sandbox_id, len(code), review_result, source="execute_code"
                    )

                    if review_result.decision == "reject":
                        # Code rejected by LLM filter
                        logger.error(
                            f"❌ CODE REJECTED by LLM filter for sandbox {sandbox_id}"
                        )
                        logger.error(
                            f"   Threats: {', '.join(review_result.threats_detected)}"
                        )

                        error_message = f"""
🚫 CODE REJECTED BY SECURITY FILTER

The LLM security agent has identified potential threats in your code and rejected execution.

Decision: REJECT
Confidence: {review_result.confidence:.1%}

Threats Detected:
{chr(10).join(f'  - {threat}' for threat in review_result.threats_detected)}

Reasons:
{chr(10).join(f'  - {reason}' for reason in review_result.reasons)}
"""

                        if review_result.safe_alternative:
                            error_message += f"\n\nSuggested Safe Alternative:\n{review_result.safe_alternative}\n"

                        error_message += "\n" + "=" * 60
                        error_message += "\nYour Code:\n" + "=" * 60 + "\n"
                        error_message += code
                        error_message += "\n" + "=" * 60

                        raise ValueError(error_message)
                    else:
                        logger.info(
                            f"✅ CODE APPROVED by LLM filter for sandbox {sandbox_id}"
                        )

                except asyncio.TimeoutError:
                    logger.error("⏱️ LLM filter timed out after 30 seconds")
                    logger.warning(
                        "⚠️ Proceeding with code execution WITHOUT LLM review"
                    )
                    # Log skipped review due to timeout
                    log_llm_review(
                        sandbox_id,
                        len(code),
                        {
                            "decision": "skipped",
                            "confidence": 0.0,
                            "reasons": [
                                "LLM filter timed out (>30s)",
                            ],
                            "threats_detected": [],
                            "safe_alternative": None,
                        },
                        source="execute_code",
                    )
                except Exception as e:
                    logger.error(f"❌ LLM filter error: {e}")
                    logger.warning(
                        "⚠️ Proceeding with code execution WITHOUT LLM review"
                    )
                    # Log skipped review due to error
                    log_llm_review(
                        sandbox_id,
                        len(code),
                        {
                            "decision": "skipped",
                            "confidence": 0.0,
                            "reasons": [f"LLM filter error: {e}"],
                            "threats_detected": ["review_error"],
                            "safe_alternative": None,
                        },
                        source="execute_code",
                    )
            else:
                # Log skipped review when filter unavailable
                log_llm_review(
                    sandbox_id,
                    len(code),
                    {
                        "decision": "skipped",
                        "confidence": 0.0,
                        "reasons": ["LLM code filter unavailable"],
                        "threats_detected": [],
                        "safe_alternative": None,
                    },
                    source="execute_code",
                )

        logger.info(f"Executing code in sandbox: {sandbox_id}")

        try:
            container = await asyncio.to_thread(
                docker_client.containers.get, sandbox_id
            )

            # Check if container is still running
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                raise ValueError(f"Sandbox is not running (status: {container.status})")

            ports = container.attrs["NetworkSettings"]["Ports"]
            port_mapping = ports.get(f"{SANDBOX_PORT}/tcp", [])

            if not port_mapping:
                raise ValueError("Sandbox not ready - no exposed port")

            host_port = port_mapping[0]["HostPort"]
            sandbox_url = f"http://localhost:{host_port}/execute"

            # Execute code with timeout
            try:
                response = await http_client.post(sandbox_url, json={"code": code})
            except httpx.TimeoutException:
                # Check if container crashed
                await asyncio.to_thread(container.reload)
                if container.status != "running":
                    return await SandboxManager._handle_container_crash(
                        container, sandbox_id, code
                    )
                raise ValueError("Execution timeout - code took too long to execute")
            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                # Container might have crashed or been terminated
                logger.warning(
                    f"Connection error during execution: {type(e).__name__}: {e}"
                )
                await asyncio.to_thread(container.reload)
                if container.status != "running":
                    return await SandboxManager._handle_container_crash(
                        container, sandbox_id, code
                    )
                raise ValueError(
                    f"Cannot connect to sandbox - connection error: {type(e).__name__}"
                )

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
    async def _handle_container_crash(
        container, sandbox_id: str, code: str
    ) -> Dict[str, Any]:
        """Handle container crash and collect information."""
        logger.error(f"Container {sandbox_id} crashed during execution")

        # Get container inspect data
        inspect_data = container.attrs
        state = inspect_data.get("State", {})

        exit_code = state.get("ExitCode", -1)
        error = state.get("Error", "")
        oom_killed = state.get("OOMKilled", False)

        # Get container logs with separate stdout/stderr
        try:
            stdout = await asyncio.to_thread(
                container.logs, stdout=True, stderr=False, tail=50, timestamps=True
            )
            stderr = await asyncio.to_thread(
                container.logs, stdout=False, stderr=True, tail=50, timestamps=True
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Combine for display
            logs_parts = []
            if stdout_str.strip():
                logs_parts.append(f"STDOUT:\n{stdout_str}")
            if stderr_str.strip():
                logs_parts.append(f"STDERR:\n{stderr_str}")

            logs_str = "\n\n".join(logs_parts) if logs_parts else "No logs available"
        except Exception as e:
            logs_str = f"Failed to retrieve logs: {e}"

        # Determine crash reason
        crash_reason = "UNKNOWN"
        mining_detected = False

        if oom_killed:
            crash_reason = "OUT_OF_MEMORY"
        elif exit_code == 137:
            # Check if it was PID limit
            if "fork" in logs_str.lower() or "process" in logs_str.lower():
                crash_reason = "PROCESS_LIMIT_EXCEEDED (possible fork bomb)"
            else:
                crash_reason = "KILLED (SIGKILL)"
        elif exit_code == 139:
            crash_reason = "SEGMENTATION_FAULT"

        # Get crash info from monitor if available
        crash_details = ""
        if MONITORING_ENABLED:
            monitor = get_monitor()
            crash_info = monitor.get_crash_by_container(sandbox_id)
            if crash_info:
                # Check if it was mining detection
                if "mining" in crash_info.get("crash_reason", "").lower():
                    crash_reason = "🔪 TERMINATED BY MINING DETECTOR"
                    mining_detected = True

                crash_details = (
                    f"\n\n🔍 Monitor Detection:\n"
                    f"  Reason: {crash_info['crash_reason']}\n"
                    f"  Exit Code: {crash_info['exit_code']}\n"
                    f"  OOM Killed: {crash_info['oom_killed']}"
                )

        # Build appropriate error message based on crash reason
        if mining_detected:
            error_message = f"""
⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED

🔪 The monitoring system detected cryptocurrency mining activity and terminated the container.

{crash_details}

Exit Code: {exit_code}

⚠️  Mining Activity Indicators:
- Sustained high CPU usage (near 50% quota limit)
- Continuous hashing operations detected
- Pattern matching: mining/cryptocurrency keywords
- ML model flagged the activity as suspicious

Code that triggered the detection:
{'-' * 60}
{code[:500]}{'...' if len(code) > 500 else ''}
{'-' * 60}

Container Logs (last 50 lines):
{'-' * 60}
{logs_str}
{'-' * 60}

📊 This is a security feature that protects against:
- Cryptocurrency mining abuse
- Resource exhaustion attacks  
- Unauthorized compute usage

Check the observability dashboard for detailed metrics and detection logs.
"""
        else:
            error_message = f"""
🔥 CONTAINER CRASHED DURING EXECUTION

Crash Reason: {crash_reason}
Exit Code: {exit_code}
OOM Killed: {oom_killed}
{f"Error: {error}" if error else ""}
{crash_details}

Code that caused the crash:
{'-' * 60}
{code[:500]}{'...' if len(code) > 500 else ''}
{'-' * 60}

Container Logs (last 50 lines):
{'-' * 60}
{logs_str}
{'-' * 60}

Troubleshooting:
- If OOM: The code used too much memory (limit: 512MB). Try processing smaller datasets.
- If PROCESS_LIMIT: Too many processes created (limit: 100). Avoid fork bombs and excessive subprocess creation.
- If SIGKILL: The process was forcefully terminated, usually due to resource limits.
- If SEGFAULT: The code caused a segmentation fault (memory access error).

Check the observability dashboard for detailed metrics.
"""

        # Clean up crashed container
        sandboxes.pop(sandbox_id, None)
        sandbox_owners.pop(sandbox_id, None)

        return {
            "status": "crashed",
            "results": [{"type": "error", "content": error_message}],
            "crash_info": {
                "exit_code": exit_code,
                "oom_killed": oom_killed,
                "reason": crash_reason,
                "logs": logs_str,
                "mining_detected": mining_detected,
            },
        }

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
    tools = [
        Tool(
            name="create_sandbox",
            description=(
                "Create a new isolated Python code execution sandbox. "
                "Each sandbox is a Docker container with resource limits. "
                "IMPORTANT: Sandboxes are automatically deleted after code execution by default. "
                "Set auto_cleanup=false in execute_python/execute_from_url to keep them alive. "
                "Idle sandboxes auto-delete after 5 minutes."
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
                "CRITICAL: Unless you need to reuse the sandbox for multiple executions, "
                "DO NOT set auto_cleanup=false. Leaving containers running wastes resources "
                "and causes continuous ML monitoring. Default behavior (auto_cleanup=true or omitted) "
                "automatically deletes the sandbox after execution."
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
                    "auto_cleanup": {
                        "type": "boolean",
                        "description": "Optional: Set to false ONLY if you need to reuse the sandbox for multiple executions. If omitted or true, sandbox is automatically deleted after execution to prevent resource waste.",
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
        Tool(
            name="execute_from_url",
            description=(
                "Fetch Python code from a URL and execute it in a sandbox. "
                "This tool will download code from the provided URL and run it in an isolated environment. "
                "Useful for running code from GitHub gists, pastebin, or other code sharing services. "
                "The URL must be publicly accessible (http/https). "
                "Maximum code size: 1MB. "
                "IMPORTANT: The sandbox is automatically deleted after execution by default (auto_cleanup=true). "
                "Set auto_cleanup=false to keep the sandbox alive for reuse."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sandbox_id": {
                        "type": "string",
                        "description": "The ID of the sandbox to execute code in",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to fetch Python code from (must be http/https)",
                    },
                    "auto_cleanup": {
                        "type": "boolean",
                        "description": "Optional: Set to false ONLY if you need to reuse the sandbox for multiple executions. If omitted or true, sandbox is automatically deleted after execution to prevent resource waste.",
                    },
                },
                "required": ["sandbox_id", "url"],
            },
        ),
    ]

    # Add monitoring tools if available
    if MONITORING_ENABLED:
        tools.extend(
            [
                Tool(
                    name="inspect_container",
                    description=(
                        "Get detailed information about a container using Docker inspect. "
                        "Returns comprehensive metadata including resource limits, network settings, "
                        "state, configuration, and more. Useful for debugging and monitoring."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sandbox_id": {
                                "type": "string",
                                "description": "The ID of the sandbox to inspect",
                            }
                        },
                        "required": ["sandbox_id"],
                    },
                ),
                Tool(
                    name="get_container_metrics",
                    description=(
                        "Get real-time resource utilization metrics for a container. "
                        "Returns CPU usage, memory usage, network I/O, and block I/O statistics. "
                        "Helpful for monitoring performance and resource consumption."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sandbox_id": {
                                "type": "string",
                                "description": "The ID of the sandbox to get metrics for",
                            }
                        },
                        "required": ["sandbox_id"],
                    },
                ),
            ]
        )

    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    start_time = time.time()
    status = "success"
    result_text = ""

    try:
        if name == "create_sandbox":
            result = await SandboxManager.create_sandbox(current_session_id)
            result_text = (
                f"✅ Sandbox created successfully!\n\n"
                f"Sandbox ID: {result['sandbox_id']}\n"
                f"Status: {result['status']}\n\n"
                f"You can now execute Python code using execute_python with this sandbox_id."
            )

            # Log request
            log_request(name, arguments, result_text, "success")

            return [TextContent(type="text", text=result_text)]

        elif name == "execute_python":
            sandbox_id = arguments.get("sandbox_id")
            code = arguments.get("code")
            auto_cleanup = arguments.get("auto_cleanup", True)

            if not sandbox_id or not code:
                result_text = "❌ Error: Both sandbox_id and code are required"
                log_request(name, arguments, result_text, "error")
                return [TextContent(type="text", text=result_text)]

            result = await SandboxManager.execute_code(
                sandbox_id, code, current_session_id
            )

            # Auto-cleanup if requested
            cleanup_message = ""
            if auto_cleanup and result.get("status") != "crashed":
                try:
                    # Trigger final ML analysis before deletion
                    if MONITORING_ENABLED:
                        monitor = get_monitor()
                        logger.info(
                            f"Triggering final ML analysis for {sandbox_id} before deletion..."
                        )
                        try:
                            # Get the container and do one final metrics collection + analysis
                            container = await asyncio.to_thread(
                                docker_client.containers.get, sandbox_id
                            )
                            await monitor.collect_container_metrics(container)
                            logger.info(f"Final ML analysis completed for {sandbox_id}")
                        except Exception as e:
                            logger.warning(f"Failed to run final ML analysis: {e}")

                    await SandboxManager.delete_sandbox(sandbox_id, current_session_id)
                    cleanup_message = (
                        "\n\n🗑️  Sandbox automatically deleted after execution."
                    )
                    logger.info(f"Auto-cleaned up sandbox: {sandbox_id}")
                except Exception as e:
                    logger.warning(f"Failed to auto-cleanup sandbox {sandbox_id}: {e}")
                    cleanup_message = (
                        f"\n\n⚠️  Warning: Failed to auto-cleanup sandbox: {e}"
                    )

            # Format results
            output_parts = []

            # Check if container crashed
            if result.get("status") == "crashed":
                output_parts.append("🔥 CONTAINER CRASHED 🔥\n")
                crash_info = result.get("crash_info", {})

                for item in result.get("results", []):
                    if item["type"] == "error":
                        output_parts.append(item["content"])

                result_text = "\n".join(output_parts)
                log_request(
                    name,
                    {"sandbox_id": sandbox_id, "code_length": len(code)},
                    result_text,
                    "crashed",
                )
                return [TextContent(type="text", text=result_text)]

            # Normal execution
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

            result_text = "\n\n".join(output_parts) + cleanup_message
            log_request(
                name,
                {
                    "sandbox_id": sandbox_id,
                    "code_length": len(code),
                    "auto_cleanup": auto_cleanup,
                },
                result_text,
                "success",
            )
            return [TextContent(type="text", text=result_text)]

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

        elif name == "execute_from_url":
            sandbox_id = arguments.get("sandbox_id")
            url = arguments.get("url")
            auto_cleanup = arguments.get("auto_cleanup", True)

            if not sandbox_id or not url:
                return [
                    TextContent(
                        type="text",
                        text="❌ Error: Both sandbox_id and url are required",
                    )
                ]

            # Fetch code from URL
            try:
                fetch_result = await SandboxManager.fetch_code_from_url(url)
                code = fetch_result["code"]

                logger.info(
                    f"Fetched {fetch_result['size']} bytes from {url}, executing in {sandbox_id}"
                )
            except ValueError as e:
                result_text = f"❌ Error fetching code from URL:\n{str(e)}"
                log_request(
                    name, {"sandbox_id": sandbox_id, "url": url}, result_text, "error"
                )
                return [TextContent(type="text", text=result_text)]
            except Exception as e:
                result_text = f"❌ Unexpected error fetching code:\n{str(e)}"
                log_request(
                    name, {"sandbox_id": sandbox_id, "url": url}, result_text, "error"
                )
                return [TextContent(type="text", text=result_text)]

            # Execute the fetched code (will go through LLM filter if enabled)
            try:
                logger.info(
                    f"🔍 Executing fetched code in sandbox {sandbox_id} (will be filtered by LLM)"
                )
                result = await SandboxManager.execute_code(
                    sandbox_id, code, current_session_id
                )
            except ValueError as e:
                # Handle LLM rejection or sandbox validation errors
                error_str = str(e)

                # Check if it's an LLM rejection (contains specific markers)
                if "CODE REJECTED BY SECURITY FILTER" in error_str or "🚫" in error_str:
                    status = "rejected"
                    result_text = f"📥 Fetched code from: {url}\n   Size: {fetch_result['size']} bytes\n\n{error_str}"
                    logger.warning(f"❌ LLM REJECTED code from URL: {url}")
                else:
                    # Other validation errors (sandbox not found, access denied, etc.)
                    status = "error"
                    result_text = f"📥 Fetched code from: {url}\n   Size: {fetch_result['size']} bytes\n\n❌ {error_str}"
                    logger.error(f"❌ Validation error for URL execution: {error_str}")

                log_request(
                    name,
                    {"sandbox_id": sandbox_id, "url": url, "code_length": len(code)},
                    result_text,
                    status,
                )
                return [TextContent(type="text", text=result_text)]
            except Exception as e:
                # Handle execution errors (container not running, etc.)
                result_text = f"📥 Fetched code from: {url}\n   Size: {fetch_result['size']} bytes\n\n❌ Execution failed:\n{str(e)}"
                logger.error(f"❌ Execution error: {str(e)}")
                log_request(
                    name,
                    {"sandbox_id": sandbox_id, "url": url, "code_length": len(code)},
                    result_text,
                    "error",
                )
                return [TextContent(type="text", text=result_text)]

            # Auto-cleanup if requested
            cleanup_message = ""
            if auto_cleanup and result.get("status") != "crashed":
                try:
                    # Trigger final ML analysis before deletion
                    if MONITORING_ENABLED:
                        monitor = get_monitor()
                        logger.info(
                            f"Triggering final ML analysis for {sandbox_id} before deletion..."
                        )
                        try:
                            # Get the container and do one final metrics collection + analysis
                            container = await asyncio.to_thread(
                                docker_client.containers.get, sandbox_id
                            )
                            await monitor.collect_container_metrics(container)
                            logger.info(f"Final ML analysis completed for {sandbox_id}")
                        except Exception as e:
                            logger.warning(f"Failed to run final ML analysis: {e}")

                    await SandboxManager.delete_sandbox(sandbox_id, current_session_id)
                    cleanup_message = (
                        "\n\n🗑️  Sandbox automatically deleted after execution."
                    )
                    logger.info(f"Auto-cleaned up sandbox: {sandbox_id}")
                except Exception as e:
                    logger.warning(f"Failed to auto-cleanup sandbox {sandbox_id}: {e}")
                    cleanup_message = (
                        f"\n\n⚠️  Warning: Failed to auto-cleanup sandbox: {e}"
                    )

            # Format results
            output_parts = []

            # Add URL information
            output_parts.append(f"📥 Fetched code from: {url}")
            output_parts.append(f"   Size: {fetch_result['size']} bytes")
            output_parts.append(
                f"   Content-Type: {fetch_result.get('content_type', 'unknown')}\n"
            )

            # Check if container crashed
            if result.get("status") == "crashed":
                output_parts.append("🔥 CONTAINER CRASHED 🔥\n")
                crash_info = result.get("crash_info", {})

                for item in result.get("results", []):
                    if item["type"] == "error":
                        output_parts.append(item["content"])

                result_text = "\n".join(output_parts)
                log_request(
                    name,
                    {"sandbox_id": sandbox_id, "url": url, "code_length": len(code)},
                    result_text,
                    "crashed",
                )
                return [TextContent(type="text", text=result_text)]

            # Normal execution
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

            result_text = "\n\n".join(output_parts) + cleanup_message
            log_request(
                name,
                {
                    "sandbox_id": sandbox_id,
                    "url": url,
                    "code_length": len(code),
                    "auto_cleanup": auto_cleanup,
                },
                result_text,
                "success",
            )
            return [TextContent(type="text", text=result_text)]

        elif name == "inspect_container" and MONITORING_ENABLED:
            sandbox_id = arguments.get("sandbox_id")

            if not sandbox_id:
                return [
                    TextContent(type="text", text="❌ Error: sandbox_id is required")
                ]

            # Verify ownership
            if sandbox_owners.get(sandbox_id) != current_session_id:
                return [
                    TextContent(
                        type="text", text="❌ Error: Sandbox not found or access denied"
                    )
                ]

            monitor = get_monitor()
            details = monitor.get_container_details(sandbox_id)

            if not details:
                return [TextContent(type="text", text="❌ Error: Container not found")]

            output = [
                f"🔍 Container Inspection: {details['name']}\n",
                f"📋 Basic Info:",
                f"  • ID: {details['id']}",
                f"  • Image: {details['image']}",
                f"  • Status: {details['status']}",
                f"  • PID: {details['pid']}",
                f"  • Created: {details['created']}",
                f"\n⚙️  Resource Limits:",
                f"  • Memory: {details['memory_limit'] / 1024 / 1024:.0f} MB",
                f"  • CPU Quota: {details['cpu_quota']}",
                f"  • CPU Period: {details['cpu_period']}",
                f"\n🌐 Network:",
                f"  • IP: {details['ip_address'] or 'N/A'}",
                f"  • Networks: {', '.join(details['networks']) or 'None'}",
                f"\n🏷️  Labels: {details['labels']}",
            ]

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "get_container_metrics" and MONITORING_ENABLED:
            sandbox_id = arguments.get("sandbox_id")

            if not sandbox_id:
                return [
                    TextContent(type="text", text="❌ Error: sandbox_id is required")
                ]

            # Verify ownership
            if sandbox_owners.get(sandbox_id) != current_session_id:
                return [
                    TextContent(
                        type="text", text="❌ Error: Sandbox not found or access denied"
                    )
                ]

            monitor = get_monitor()
            metrics = monitor.get_container_metrics(sandbox_id, limit=1)

            if not metrics:
                return [
                    TextContent(
                        type="text",
                        text="❌ Error: No metrics available. Container may not be running.",
                    )
                ]

            latest = metrics[-1]

            output = [
                f"📊 Container Metrics: {latest['name']}\n",
                f"💻 CPU:",
                f"  • Current: {latest['cpu_percent']}%",
                f"\n💾 Memory:",
                f"  • Usage: {latest['memory_usage_mb']:.1f} MB",
                f"  • Limit: {latest['memory_limit_mb']:.1f} MB",
                f"  • Percent: {latest['memory_percent']:.1f}%",
                f"\n🌐 Network I/O:",
                f"  • RX: {latest['network_rx_bytes'] / 1024:.1f} KB",
                f"  • TX: {latest['network_tx_bytes'] / 1024:.1f} KB",
                f"\n💿 Disk I/O:",
                f"  • Read: {latest['block_read_bytes'] / 1024:.1f} KB",
                f"  • Write: {latest['block_write_bytes'] / 1024:.1f} KB",
                f"\n⏱️  Status: {latest['status']}",
            ]

            return [TextContent(type="text", text="\n".join(output))]

        else:
            result_text = f"❌ Unknown tool: {name}"
            log_request(name, arguments, result_text, "error")
            return [TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Tool error ({name}): {e}", exc_info=True)
        result_text = f"❌ Error: {str(e)}"
        log_request(name, arguments, result_text, "error")
        return [TextContent(type="text", text=result_text)]


async def main():
    """Run the MCP server."""
    logger.info("Starting Code Sandbox MCP Server")
    logger.info(f"Configuration:")
    logger.info(f"  Image: {IMAGE_NAME}")
    logger.info(f"  Idle Timeout: {IDLE_TIMEOUT}s")
    logger.info(f"  Max Sandboxes: {MAX_SANDBOXES}")
    logger.info(f"  Monitoring: {'Enabled' if MONITORING_ENABLED else 'Disabled'}")
    logger.info(
        f"  🛡️  LLM Code Filter: {'Enabled' if CODE_FILTER_ENABLED else 'Disabled'}"
    )
    logger.info(f"  📝 Request History: {os.path.abspath(HISTORY_FILE)}")
    logger.info(f"  📂 Working Directory: {os.getcwd()}")

    if CODE_FILTER_ENABLED:
        logger.info(
            f"     → All code execution (execute_python & execute_from_url) will be"
        )
        logger.info(f"       analyzed by Ollama LLM before running in sandboxes")
        logger.info(f"     → Malicious code will be rejected automatically")

    # Start monitoring if enabled
    monitoring_task = None
    if MONITORING_ENABLED:
        monitor = get_monitor()
        monitoring_task = asyncio.create_task(monitor.start_monitoring())
        logger.info("Container monitoring started")

    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_idle_sandboxes())

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        cleanup_task.cancel()
        if monitoring_task:
            monitoring_task.cancel()
        logger.info("MCP Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
