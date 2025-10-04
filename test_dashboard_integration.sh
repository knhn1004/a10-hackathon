#!/bin/bash
# Test Dashboard Integration for LLM and ML Security Layers

echo "🧪 Testing Dashboard Integration"
echo "================================"
echo ""

# Check if services are running
echo "1️⃣  Checking if dashboard is running..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "   ✅ Dashboard is running (port 8080)"
else
    echo "   ❌ Dashboard is NOT running"
    echo "      Start it with: ./run_dashboard.sh"
    exit 1
fi

echo ""
echo "2️⃣  Testing LLM Reviews API..."
LLM_RESPONSE=$(curl -s http://localhost:8080/api/llm/reviews?limit=5)
LLM_COUNT=$(echo $LLM_RESPONSE | jq -r '.count // 0')
echo "   📊 Found $LLM_COUNT LLM reviews"

if [ "$LLM_COUNT" -gt 0 ]; then
    echo "   ✅ LLM reviews are being logged"
    echo ""
    echo "   Latest review:"
    echo $LLM_RESPONSE | jq -r '.reviews[0] | "      Decision: \(.review.decision) | Confidence: \((.review.confidence * 100) | floor)% | Sandbox: \(.sandbox_id)"'
else
    echo "   ⚠️  No LLM reviews yet (run some code to generate them)"
fi

echo ""
echo "3️⃣  Testing ML Classifications API..."
ML_RESPONSE=$(curl -s http://localhost:8080/api/ml/classifications?limit=5)
ML_COUNT=$(echo $ML_RESPONSE | jq -r '.count // 0')
echo "   📊 Found $ML_COUNT ML classifications"

if [ "$ML_COUNT" -gt 0 ]; then
    echo "   ✅ ML classifications are being logged"
    echo ""
    echo "   Latest classification:"
    echo $ML_RESPONSE | jq -r '.alerts[0] | "      Prediction: \(.details.prediction) | Confidence: \((.details.confidence * 100) | floor)% | Container: \(.name)"'
else
    echo "   ⚠️  No ML classifications yet (run mining-like code to generate them)"
fi

echo ""
echo "4️⃣  Checking log files..."

if [ -f "llm_reviews.json" ]; then
    REVIEW_COUNT=$(jq '. | length' llm_reviews.json)
    echo "   ✅ llm_reviews.json exists ($REVIEW_COUNT total reviews)"
else
    echo "   ⚠️  llm_reviews.json not created yet"
fi

echo ""
echo "5️⃣  Testing dashboard UI endpoints..."

# Test if dashboard HTML loads
if curl -s http://localhost:8080 | grep -q "Code Sandbox Observability"; then
    echo "   ✅ Dashboard HTML loads correctly"
else
    echo "   ❌ Dashboard HTML not loading"
fi

# Test if ML tab exists
if curl -s http://localhost:8080 | grep -q "ML Model"; then
    echo "   ✅ ML Model tab exists"
else
    echo "   ❌ ML Model tab missing"
fi

# Test if LLM tab exists
if curl -s http://localhost:8080 | grep -q "LLM Reviews"; then
    echo "   ✅ LLM Reviews tab exists"
else
    echo "   ❌ LLM Reviews tab missing"
fi

echo ""
echo "6️⃣  Testing API response times..."

LLM_TIME=$(curl -s -w "%{time_total}" -o /dev/null http://localhost:8080/api/llm/reviews)
echo "   🕐 LLM Reviews API: ${LLM_TIME}s"

ML_TIME=$(curl -s -w "%{time_total}" -o /dev/null http://localhost:8080/api/ml/classifications)
echo "   🕐 ML Classifications API: ${ML_TIME}s"

ALERTS_TIME=$(curl -s -w "%{time_total}" -o /dev/null http://localhost:8080/api/alerts)
echo "   🕐 All Alerts API: ${ALERTS_TIME}s"

echo ""
echo "================================"
echo "✅ Integration Test Complete!"
echo ""
echo "Dashboard: http://localhost:8080"
echo "  • LLM Reviews tab: Shows Ollama code analysis"
echo "  • ML Model tab: Shows Random Forest classifications"
echo ""

if [ "$LLM_COUNT" -eq 0 ] && [ "$ML_COUNT" -eq 0 ]; then
    echo "💡 To generate test data:"
    echo "   1. Use Claude to execute code via MCP"
    echo "   2. Try safe code: print('hello')"
    echo "   3. Try malicious code: os.system('rm -rf /')"
    echo "   4. Try mining code: while True: hashlib.sha256(...)"
    echo ""
fi

