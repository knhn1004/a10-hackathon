#!/usr/bin/env python3
"""
Ollama MCP Client

Connects a local Ollama model to the MCP code sandbox server,
allowing local LLMs to execute Python code in sandboxes.

Usage:
    python ollama_mcp_client.py --model llama3.1:latest
"""

import asyncio
import json
import sys
from typing import Any, Dict, List
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class OllamaMCPClient:
    """Bridge between Ollama and MCP code sandbox."""

    def __init__(
        self,
        ollama_model: str = "llama3.1:latest",
        ollama_url: str = "http://localhost:11434",
    ):
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.mcp_session = None
        self.stdio_context = None
        self.session_context = None
        self.tools = []
        self.conversation_history = []

    async def start_mcp_server(self):
        """Start and connect to the MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_server.py"],
            env={
                "SANDBOX_IMAGE": "code-sandbox:latest",
                "SANDBOX_TIMEOUT": "300",
                "MAX_SANDBOXES": "10",
            },
        )

        print("🔌 Connecting to MCP server...")

        # Keep context managers alive
        self.stdio_context = stdio_client(server_params)
        read_stream, write_stream = await self.stdio_context.__aenter__()

        self.session_context = ClientSession(read_stream, write_stream)
        self.mcp_session = await self.session_context.__aenter__()

        await self.mcp_session.initialize()
        print("✅ Connected to MCP server\n")

        # Get available tools
        tools_response = await self.mcp_session.list_tools()
        self.tools = tools_response.tools
        print(f"📋 Available tools: {len(self.tools)}")
        for tool in self.tools:
            print(f"   • {tool.name}: {tool.description[:60]}...")
        print()

    async def call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """Call Ollama API."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        messages.extend(self.conversation_history)

        # Add current message
        messages.append({"role": "user", "content": prompt})

        response = await self.http_client.post(
            f"{self.ollama_url}/api/chat",
            json={"model": self.ollama_model, "messages": messages, "stream": False},
        )

        if not response.is_success:
            raise Exception(f"Ollama API error: {response.text}")

        result = response.json()
        assistant_message = result["message"]["content"]

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_message}
        )

        return assistant_message

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool."""
        print(f"\n🔧 Calling tool: {tool_name}")
        if arguments:
            print(f"   Arguments: {json.dumps(arguments, indent=2)}")

        result = await self.mcp_session.call_tool(tool_name, arguments)

        # Extract text content
        response_text = ""
        for item in result.content:
            if hasattr(item, "text"):
                response_text += item.text

        print(f"✅ Tool result:\n{response_text}\n")
        return response_text

    def create_system_prompt(self) -> str:
        """Create system prompt with tool descriptions."""
        tools_desc = "\n".join(
            [f"- {tool.name}: {tool.description}" for tool in self.tools]
        )

        return f"""You are an AI assistant with access to a code execution sandbox.

Available tools:
{tools_desc}

When you need to use a tool, respond with a JSON object in this format:
{{"tool": "tool_name", "arguments": {{"arg1": "value1"}}}}

If you need to execute Python code:
1. First call create_sandbox to get a sandbox_id
2. Then call execute_python with the sandbox_id and code
3. You can call execute_python multiple times with the same sandbox_id

Always explain what you're doing and show the results to the user."""

    async def process_tool_call(self, response: str) -> str:
        """Process potential tool calls in the response."""
        # Try to find JSON tool calls
        try:
            # Look for JSON objects
            if "tool" in response and "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    tool_call = json.loads(response[start:end])

                    if "tool" in tool_call:
                        tool_name = tool_call["tool"]
                        arguments = tool_call.get("arguments", {})

                        result = await self.call_mcp_tool(tool_name, arguments)

                        # Ask Ollama to interpret the result
                        interpretation = await self.call_ollama(
                            f"The tool {tool_name} returned:\n{result}\n\nPlease summarize this result for the user.",
                            system_prompt=None,
                        )

                        return interpretation
        except json.JSONDecodeError:
            pass

        return response

    async def chat(self, user_message: str) -> str:
        """Chat with Ollama and handle tool calls."""
        print(f"\n💬 You: {user_message}")
        print(f"🤖 {self.ollama_model} thinking...\n")

        # Get response from Ollama
        response = await self.call_ollama(
            user_message, system_prompt=self.create_system_prompt()
        )

        # Process potential tool calls
        final_response = await self.process_tool_call(response)

        print(f"🤖 {self.ollama_model}: {final_response}\n")
        return final_response

    async def interactive_loop(self):
        """Interactive chat loop."""
        print("=" * 70)
        print(f"🦙 Ollama MCP Client - Model: {self.ollama_model}")
        print("=" * 70)
        print("\nType your messages below. Type 'quit' or 'exit' to stop.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Goodbye!")
                    break

                if not user_input:
                    continue

                await self.chat(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    async def cleanup(self):
        """Cleanup resources."""
        await self.http_client.aclose()
        if self.session_context:
            try:
                await self.session_context.__aexit__(None, None, None)
            except Exception:
                pass
        if self.stdio_context:
            try:
                await self.stdio_context.__aexit__(None, None, None)
            except Exception:
                pass


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ollama MCP Client")
    parser.add_argument(
        "--model", default="llama3.1:latest", help="Ollama model to use"
    )
    parser.add_argument(
        "--ollama-url", default="http://localhost:11434", help="Ollama server URL"
    )
    args = parser.parse_args()

    client = OllamaMCPClient(ollama_model=args.model, ollama_url=args.ollama_url)

    try:
        await client.start_mcp_server()
        await client.interactive_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
