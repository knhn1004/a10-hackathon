#!/usr/bin/env python3
"""
Test the MCP server locally
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Test the code sandbox MCP server."""
    print("🧪 Testing Code Sandbox MCP Server\n")

    # Start the server
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        env={
            "SANDBOX_IMAGE": "code-sandbox:latest",
            "SANDBOX_TIMEOUT": "300",
            "MAX_SANDBOXES": "10",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            print("✅ MCP session initialized\n")

            # List tools
            print("📋 Available Tools:")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description[:60]}...")
            print()

            # Test 1: Create sandbox
            print("1️⃣  Creating sandbox...")
            result = await session.call_tool("create_sandbox", {})
            print(f"   {result.content[0].text}\n")

            # Extract sandbox_id from result
            sandbox_id = None
            for line in result.content[0].text.split("\n"):
                if "Sandbox ID:" in line:
                    sandbox_id = line.split("Sandbox ID:")[1].strip()
                    break

            if not sandbox_id:
                print("❌ Failed to get sandbox ID")
                return

            # Test 2: Execute simple code
            print("2️⃣  Executing simple Python code...")
            code1 = """
print("Hello from MCP!")
print(f"2 + 2 = {2 + 2}")
x = [1, 2, 3, 4, 5]
print(f"Sum: {sum(x)}")
"""
            result = await session.call_tool(
                "execute_python", {"sandbox_id": sandbox_id, "code": code1}
            )
            print(f"   {result.content[0].text}\n")

            # Test 3: Execute code with matplotlib
            print("3️⃣  Creating matplotlib plot...")
            code2 = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 2*np.pi, 100)
y = np.sin(x)

plt.figure(figsize=(8, 5))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True, alpha=0.3)
plt.show()

print("Plot generated!")
"""
            result = await session.call_tool(
                "execute_python", {"sandbox_id": sandbox_id, "code": code2}
            )
            print(f"   {result.content[0].text}\n")

            # Test 4: List sandboxes
            print("4️⃣  Listing sandboxes...")
            result = await session.call_tool("list_sandboxes", {})
            print(f"   {result.content[0].text}\n")

            # Test 5: Test error handling
            print("5️⃣  Testing error handling...")
            code3 = "print(undefined_variable)"
            result = await session.call_tool(
                "execute_python", {"sandbox_id": sandbox_id, "code": code3}
            )
            print(f"   {result.content[0].text}\n")

            # Test 6: Delete sandbox
            print("6️⃣  Deleting sandbox...")
            result = await session.call_tool(
                "delete_sandbox", {"sandbox_id": sandbox_id}
            )
            print(f"   {result.content[0].text}\n")

            print("✨ All tests completed!")


if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_server())
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
