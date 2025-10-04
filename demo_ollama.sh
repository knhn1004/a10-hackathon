#!/bin/bash
# Demo script for Ollama MCP Client

echo "🦙 Ollama Code Sandbox Demo"
echo "============================"
echo ""
echo "This will start an interactive session with your local Ollama model."
echo "The model can execute Python code in isolated Docker containers!"
echo ""
echo "Available models:"
echo "  - llama3.1:latest (recommended)"
echo "  - codeqwen:latest (specialized in code)"
echo "  - mistral:instruct"
echo ""
echo "Try asking:"
echo '  • "Create a sandbox and calculate fibonacci(10)"'
echo '  • "Plot a sine wave from 0 to 2π"'
echo '  • "Calculate the mean of [1,2,3,4,5] using numpy"'
echo ""
echo "Starting in 3 seconds..."
sleep 3

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
poetry run python ollama_mcp_client.py --model llama3.1:latest

