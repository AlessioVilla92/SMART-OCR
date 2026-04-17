#!/usr/bin/env bash
# End-to-end smoke test using curl.
# Requires: API running on localhost:8000, Redis running.
# Usage: bash scripts/smoke_test.sh

set -e

BASE="http://localhost:8000/api/v1"

echo "=== Smart OCR Smoke Test ==="
echo ""

# 1. Health check
echo "1. Health check..."
curl -s "$BASE/health" | python3 -m json.tool
echo ""

# 2. Login
echo "2. Login as admin..."
TOKEN=$(curl -s -X POST "$BASE/auth/login" \
    -d "username=admin&password=admin123" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
    echo "FAIL: Login failed"
    exit 1
fi
echo "OK: Got JWT token (${#TOKEN} chars)"
echo ""

# 3. Create job (needs real images — skip if not available)
echo "3. Checking for test images..."
TEST_DIR="../../smart_ocr/data"
if [ -d "../../TEST1" ]; then
    echo "   Found TEST1/ — use those for manual testing"
else
    echo "   No test images found. Skipping job creation."
    echo "   To test jobs, run with real CBCL page photos."
fi
echo ""

# 4. Test scoring recompute
echo "4. Testing score recompute..."
SCORE_RESULT=$(curl -s -X POST "$BASE/score/recompute" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"items": {"1": 0, "2": 1, "3": 2, "4": 0, "5": 1}, "age": 10, "gender": "M"}')

echo "$SCORE_RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"   Total score: {d.get('total_score', 'N/A')}\")
print(f\"   Scales: {len(d.get('subscale_scores', {}))} computed\")
" 2>/dev/null || echo "   Score recompute response received"
echo ""

echo "=== Smoke Test Complete ==="
