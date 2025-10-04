#!/bin/bash
# Test the multi-user auth proxy setup

set -e

echo "🧪 Testing Multi-User Auth Proxy Setup"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get test token (use env var or prompt)
if [ -z "$TEST_TOKEN" ]; then
    TEST_TOKEN="${MCP_API_TOKEN:-mcp_vdRW0jLXVArbsKL5wKGut_l1kr0NcfC4RSl4TKiu4Jw}"
fi

echo "Using token: ${TEST_TOKEN:0:20}..."
echo "(Set TEST_TOKEN env var to test with a different token)"
echo ""

# Test 1: Dashboard is running
echo "Test 1: Dashboard API..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard is running${NC}"
else
    echo -e "${RED}❌ Dashboard not running. Start it with: ./run_dashboard.sh${NC}"
    exit 1
fi
echo ""

# Test 2: Token validation directly
echo "Test 2: Token validation..."
VALIDATION=$(curl -s -X POST "http://localhost:8080/api/tokens/validate?token=$TEST_TOKEN")
if echo "$VALIDATION" | grep -q '"valid":true'; then
    echo -e "${GREEN}✅ Token is valid${NC}"
    echo "   User: $(echo $VALIDATION | grep -o '"user_id":"[^"]*"' | cut -d'"' -f4)"
else
    echo -e "${RED}❌ Token validation failed${NC}"
    echo "   Response: $VALIDATION"
    exit 1
fi
echo ""

# Test 3: MCPO backend
echo "Test 3: MCPO backend (port 8001)..."
if curl -s http://localhost:8001/openapi.json > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MCPO backend is responding${NC}"
else
    echo -e "${YELLOW}⚠️  MCPO backend not running (will be started by script)${NC}"
fi
echo ""

# Test 4: Auth proxy
echo "Test 4: Auth proxy (port 8000)..."
if curl -s http://localhost:8000/proxy-health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Auth proxy is running${NC}"
    
    # Test with valid token
    echo ""
    echo "Test 4a: Valid token..."
    RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/openapi.json)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Auth proxy accepts valid token${NC}"
    else
        echo -e "${RED}❌ Auth proxy rejected valid token (HTTP $HTTP_CODE)${NC}"
    fi
    
    # Test with invalid token
    echo ""
    echo "Test 4b: Invalid token..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid_token" http://localhost:8000/openapi.json)
    if [ "$HTTP_CODE" = "401" ]; then
        echo -e "${GREEN}✅ Auth proxy rejects invalid token${NC}"
    else
        echo -e "${YELLOW}⚠️  Expected 401, got HTTP $HTTP_CODE${NC}"
    fi
    
    # Test without token
    echo ""
    echo "Test 4c: No token..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/openapi.json)
    if [ "$HTTP_CODE" = "401" ]; then
        echo -e "${GREEN}✅ Auth proxy requires token${NC}"
    else
        echo -e "${YELLOW}⚠️  Expected 401, got HTTP $HTTP_CODE${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Auth proxy not running (will be started by script)${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}🎉 Tests complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run: ./run_with_cloudflare.sh"
echo "  2. Choose option 2 (named tunnel) or 1 (quick)"
echo "  3. Use the public URL in ChatGPT Custom GPT"
echo "  4. Each user configures with their own dashboard token"
echo ""

