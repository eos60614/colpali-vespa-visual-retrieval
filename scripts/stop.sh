#!/bin/bash
# Stop the system (backend + frontend)

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "Stopping ColPali-Vespa Visual Retrieval System..."

# Stop backend
if [ -f logs/server.pid ]; then
    PID=$(cat logs/server.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo -e "  ${GREEN}✓${NC} Backend stopped (PID: $PID)"
    else
        echo -e "  ${RED}✗${NC} Backend not running (stale PID)"
    fi
    rm -f logs/server.pid
else
    echo "  No backend PID file found"
fi

# Stop frontend
if [ -f logs/frontend.pid ]; then
    PID=$(cat logs/frontend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo -e "  ${GREEN}✓${NC} Frontend stopped (PID: $PID)"
    else
        echo -e "  ${RED}✗${NC} Frontend not running (stale PID)"
    fi
    rm -f logs/frontend.pid
else
    echo "  No frontend PID file found"
fi

echo "Done."
