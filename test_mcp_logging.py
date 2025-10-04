#!/usr/bin/env python3
"""
Test script to verify MCP request logging works.
This simulates what happens when a request comes through MCP.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, str(Path(__file__).parent))


async def test_mcp_logging():
    """Test the MCP request logging functionality."""
    print("🧪 Testing MCP request logging...\n")

    # Import after adding to path
    from mcp_server import log_request, HISTORY_FILE

    # Simulate some MCP requests
    test_requests = [
        {
            "tool": "create_sandbox",
            "arguments": {},
            "result": "✅ Sandbox created successfully!\n\nSandbox ID: test-123\nStatus: running",
            "status": "success",
        },
        {
            "tool": "execute_python",
            "arguments": {"sandbox_id": "test-123", "code_length": 25},
            "result": "📊 Execution Status: success\n\n📝 Output:\nHello, world!",
            "status": "success",
        },
        {
            "tool": "execute_python",
            "arguments": {"sandbox_id": "test-123", "code_length": 42},
            "result": "📊 Execution Status: success\n\n📝 Output:\nThe answer is 42",
            "status": "success",
        },
        {
            "tool": "list_sandboxes",
            "arguments": {},
            "result": "📦 Active Sandboxes:\n1. test-123 (running)",
            "status": "success",
        },
        {
            "tool": "execute_python",
            "arguments": {"sandbox_id": "test-456", "code_length": 30},
            "result": "❌ Error: Sandbox not found",
            "status": "error",
        },
    ]

    # Log each request
    for i, req in enumerate(test_requests, 1):
        print(f"  [{i}/{len(test_requests)}] Logging {req['tool']}...")
        log_request(
            tool_name=req["tool"],
            arguments=req["arguments"],
            result=req["result"],
            status=req["status"],
        )

    # Verify the file was created
    print(f"\n✅ Logged {len(test_requests)} test requests")

    if Path(HISTORY_FILE).exists():
        print(f"✅ History file created: {HISTORY_FILE}")

        # Read and display the contents
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)

        print(f"\n📊 File contains {len(history)} entries:")
        for entry in history:
            print(f"   • {entry['tool']} ({entry['status']}) at {entry['timestamp']}")

        print(f"\n✨ Success! Dashboard will now show these MCP requests.")
        print(f"   Open http://localhost:8080 and click 'MCP Requests' tab")
    else:
        print(f"❌ History file was not created: {HISTORY_FILE}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_logging())
    sys.exit(0 if success else 1)
