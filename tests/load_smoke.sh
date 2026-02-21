#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://localhost:8000}"

echo "Smoke:"
curl -s "$BASE/health" >/dev/null && echo "health ok"
curl -s "$BASE/docs"  >/dev/null && echo "docs ok"

echo "Concurrency burst (dad-joke):"
for i in {1..200}; do curl -s "$BASE/dad-joke" > /dev/null & done
wait
echo "done"
