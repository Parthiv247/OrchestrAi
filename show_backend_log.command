#!/bin/bash
echo "=== BACKEND LOG (last 60 lines) ==="
cat /tmp/orchestrai_backend.log 2>/dev/null | tail -60
echo ""
echo "=== PORT 8000 STATUS ==="
lsof -i:8000 2>/dev/null || echo "Nothing on port 8000"
echo ""
echo "=== KILL STUCK CURL ==="
pkill -f "curl.*8000" 2>/dev/null && echo "Killed hanging curl" || echo "No hanging curl found"
echo ""
echo "Done. Press Enter to close."
read
