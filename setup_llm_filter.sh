#!/bin/bash
# Quick setup script for LLM Code Safety Filter

echo "🛡️  Setting up LLM Code Safety Filter"
echo "======================================"
echo ""

# Check if Ollama is installed
echo "1️⃣  Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    echo "   ✅ Ollama is installed"
else
    echo "   ❌ Ollama not found"
    echo ""
    echo "   Please install Ollama first:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    exit 1
fi

# Check if Ollama is running
echo ""
echo "2️⃣  Checking if Ollama is running..."
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "   ✅ Ollama is running"
else
    echo "   ❌ Ollama is not running"
    echo ""
    echo "   Start Ollama with: ollama serve"
    echo ""
    exit 1
fi

# Pull llama3.1 model
echo ""
echo "3️⃣  Pulling llama3.1:latest model..."
echo "   (This may take a few minutes on first run)"
ollama pull llama3.1:latest

if [ $? -eq 0 ]; then
    echo "   ✅ Model downloaded successfully"
else
    echo "   ❌ Failed to pull model"
    exit 1
fi

# Install Python dependencies
echo ""
echo "4️⃣  Installing Python dependencies..."
pip install -q -r requirements-llm-filter.txt

if [ $? -eq 0 ]; then
    echo "   ✅ Dependencies installed"
else
    echo "   ❌ Failed to install dependencies"
    exit 1
fi

# Test the filter
echo ""
echo "5️⃣  Testing the code safety filter..."
python3 << 'EOF'
import sys
try:
    from code_safety_filter import get_filter
    
    filter = get_filter()
    if filter:
        # Quick test
        safe_code = "print('Hello, world!')"
        result = filter.review_code(safe_code)
        
        if result.decision == "accept":
            print("   ✅ Filter is working correctly!")
            sys.exit(0)
        else:
            print("   ⚠️  Filter works but rejected safe code (may need tuning)")
            sys.exit(0)
    else:
        print("   ❌ Filter initialization failed")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Error testing filter: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "🎉 Setup Complete!"
    echo "======================================"
    echo ""
    echo "The LLM code safety filter is ready to use."
    echo ""
    echo "Test it with:"
    echo "  python code_safety_filter.py"
    echo ""
    echo "See documentation:"
    echo "  cat LLM_CODE_FILTER.md"
    echo ""
else
    echo ""
    echo "❌ Setup failed. Check the errors above."
    exit 1
fi

