#!/usr/bin/env python3
"""
Create sample MCP request history for testing the dashboard.
"""

import json
import time

# Create sample MCP requests
sample_requests = [
    {
        "timestamp": time.time() - 300,  # 5 minutes ago
        "tool": "create_sandbox",
        "arguments": {},
        "status": "success",
        "result_preview": "✅ Sandbox created successfully!\n\nSandbox ID: sandbox_abc123\nStatus: running",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 240,  # 4 minutes ago
        "tool": "execute_python",
        "arguments": {"sandbox_id": "sandbox_abc123", "code_length": 45},
        "status": "success",
        "result_preview": "📊 Execution Status: success\n\n📝 Output:\nHello from sandboxed Python!",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 180,  # 3 minutes ago
        "tool": "execute_python",
        "arguments": {"sandbox_id": "sandbox_abc123", "code_length": 89},
        "status": "success",
        "result_preview": "📊 Execution Status: success\n\n📝 Output:\n[1, 4, 9, 16, 25, 36, 49, 64, 81, 100]",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 120,  # 2 minutes ago
        "tool": "list_sandboxes",
        "arguments": {},
        "status": "success",
        "result_preview": "📦 Active Sandboxes (1):\n\n🟢 sandbox_abc123\n   Status: running\n   Created: 2 minutes ago",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 90,  # 1.5 minutes ago
        "tool": "execute_from_url",
        "arguments": {
            "sandbox_id": "sandbox_abc123",
            "url": "https://example.com/script.py",
        },
        "status": "success",
        "result_preview": "📊 Execution Status: success\n\n📝 Output:\nScript executed successfully!",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 60,  # 1 minute ago
        "tool": "get_container_metrics",
        "arguments": {"sandbox_id": "sandbox_abc123"},
        "status": "success",
        "result_preview": "📊 Container Metrics for sandbox_abc123:\n\nCPU: 12.5%\nMemory: 45.2 MB / 512 MB",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 45,  # 45 seconds ago
        "tool": "execute_python",
        "arguments": {"sandbox_id": "sandbox_xyz789", "code_length": 30},
        "status": "error",
        "result_preview": "❌ Error: Sandbox 'sandbox_xyz789' not found",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 30,  # 30 seconds ago
        "tool": "execute_python",
        "arguments": {"sandbox_id": "sandbox_abc123", "code_length": 55},
        "status": "crashed",
        "result_preview": "🔥 CONTAINER CRASHED 🔥\n\n❌ Error: ZeroDivisionError: division by zero",
        "session_id": "test-session",
    },
    {
        "timestamp": time.time() - 10,  # 10 seconds ago
        "tool": "delete_sandbox",
        "arguments": {"sandbox_id": "sandbox_abc123"},
        "status": "success",
        "result_preview": "✅ Sandbox deleted successfully!\n\nSandbox ID: sandbox_abc123 has been removed.",
        "session_id": "test-session",
    },
]

# Write to file
output_file = "mcp_requests.json"
with open(output_file, "w") as f:
    json.dump(sample_requests, f, indent=2)

print(f"✅ Created {len(sample_requests)} sample MCP requests in {output_file}")
print(f"\n📊 Sample requests:")
for req in sample_requests:
    print(f"   • {req['tool']} ({req['status']})")

print(f"\n✨ Now open the dashboard and click 'MCP Requests' tab to see them!")
print(f"   http://localhost:8080")
