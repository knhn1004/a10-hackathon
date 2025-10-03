#!/usr/bin/env python3
"""
Quick test of Ollama MCP client
"""
import asyncio
from ollama_mcp_client import OllamaMCPClient


async def main():
    """Test the Ollama MCP client."""
    client = OllamaMCPClient(ollama_model="llama3.1:latest")

    try:
        # Start MCP server
        await client.start_mcp_server()

        # Test 1: Simple question
        print("=" * 70)
        print("TEST 1: Simple math question")
        print("=" * 70)
        await client.chat("What is 2 + 2?")

        # Test 2: Code execution
        print("\n" + "=" * 70)
        print("TEST 2: Request code execution")
        print("=" * 70)
        await client.chat(
            "Create a sandbox and calculate the factorial of 10 using Python code"
        )

        print("\n✅ Tests completed!")

    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
