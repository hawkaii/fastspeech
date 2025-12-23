#!/bin/bash
# Helper script to test the API locally

set -e

API_URL="${API_URL:-http://localhost:8080}"

echo "Testing Indic TTS API at $API_URL"
echo "=================================="

# Test 1: Health check
echo -e "\n1. Health Check"
curl -s "$API_URL/healthz" | python3 -m json.tool || echo "FAILED"

# Test 2: List languages
echo -e "\n2. List Available Languages"
curl -s "$API_URL/languages" | python3 -m json.tool || echo "FAILED"

# Test 3: Synthesize speech (Hindi)
echo -e "\n3. Synthesize Hindi Speech"
curl -s -X POST "$API_URL/synthesize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते, यह एक परीक्षण है।",
    "language": "hindi",
    "gender": "male",
    "alpha": 1.0
  }' \
  --output /tmp/test_hindi.wav

if [ -f /tmp/test_hindi.wav ]; then
  SIZE=$(stat -f%z /tmp/test_hindi.wav 2>/dev/null || stat -c%s /tmp/test_hindi.wav)
  echo "SUCCESS: Generated audio file ($SIZE bytes)"
  echo "File saved to: /tmp/test_hindi.wav"
else
  echo "FAILED: No audio file generated"
fi

# Test 4: Synthesize with alpha tag
echo -e "\n4. Synthesize with Speed Control"
curl -s -X POST "$API_URL/synthesize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "सामान्य गति। <alpha=1.3>यह धीमा है।<alpha=0.8>यह तेज़ है।",
    "language": "hindi",
    "gender": "male"
  }' \
  --output /tmp/test_alpha.wav

if [ -f /tmp/test_alpha.wav ]; then
  SIZE=$(stat -f%z /tmp/test_alpha.wav 2>/dev/null || stat -c%s /tmp/test_alpha.wav)
  echo "SUCCESS: Generated audio with alpha tags ($SIZE bytes)"
  echo "File saved to: /tmp/test_alpha.wav"
else
  echo "FAILED: No audio file generated"
fi

echo -e "\n=================================="
echo "Tests completed!"
