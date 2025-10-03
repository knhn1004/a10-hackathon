#!/bin/bash

# Run the observability dashboard
# This starts the monitoring service and web dashboard

set -e

echo "🚀 Starting Code Sandbox Observability Dashboard"
echo ""

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Check if dependencies are installed
if ! poetry run python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    poetry install
    echo ""
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build the sandbox image if it doesn't exist
if ! docker images | grep -q "code-sandbox"; then
    echo "🔨 Building code-sandbox image..."
    docker build -t code-sandbox:latest .
    echo ""
fi

echo "✅ Starting dashboard server on http://localhost:8080"
echo ""
echo "📊 Dashboard features:"
echo "   • Real-time container metrics"
echo "   • CPU and memory usage graphs"
echo "   • Docker inspect integration"
echo "   • Resource utilization tracking"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

# Run the dashboard
poetry run python dashboard_server.py

