#!/bin/bash
# Test script for per-user MCP architecture

echo "🧪 Testing Per-User MCP Architecture"
echo "====================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"

echo "1. Testing health endpoint (no auth required)..."
HEALTH=$(curl -s "$BASE_URL/proxy-health")
echo "   Response: $HEALTH"
if echo "$HEALTH" | grep -q "ok"; then
    echo -e "   ${GREEN}✓${NC} Health check passed"
else
    echo -e "   ${RED}✗${NC} Health check failed"
    exit 1
fi
echo ""

echo "2. Testing missing auth..."
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/v1/mcp/list-tools" | tail -n 1)
if [ "$RESPONSE" = "401" ]; then
    echo -e "   ${GREEN}✓${NC} Correctly rejected unauthenticated request"
else
    echo -e "   ${RED}✗${NC} Expected 401, got $RESPONSE"
fi
echo ""

echo "3. Testing with invalid token..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer invalid-token-xyz" "$BASE_URL/v1/mcp/list-tools" | tail -n 1)
if [ "$RESPONSE" = "401" ]; then
    echo -e "   ${GREEN}✓${NC} Correctly rejected invalid token"
else
    echo -e "   ${RED}✗${NC} Expected 401, got $RESPONSE"
fi
echo ""

echo "4. Testing with valid token (requires dashboard running)..."
echo "   ${YELLOW}Note: Make sure dashboard is running and you have a valid token${NC}"
echo ""
echo "   To test manually:"
echo "   export TOKEN='your-token-here'"
echo "   curl -H \"Authorization: Bearer \$TOKEN\" $BASE_URL/v1/mcp/list-tools"
echo ""

echo "5. Checking admin sessions endpoint..."
SESSIONS=$(curl -s "$BASE_URL/admin/sessions")
echo "   Active sessions: $SESSIONS"
echo ""

echo "🎉 Basic tests complete!"
echo ""
echo "Next steps:"
echo "  1. Get a valid token from the dashboard"
echo "  2. Test with: curl -H \"Authorization: Bearer YOUR_TOKEN\" $BASE_URL/v1/mcp/list-tools"
echo "  3. Watch logs: tail -f logs/auth_proxy.log"
echo "  4. Check sessions: curl $BASE_URL/admin/sessions | jq"


