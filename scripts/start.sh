#!/bin/bash
# Start the entire system (backend + frontend)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Load nvm if available and use latest node
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && nvm use node > /dev/null 2>&1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting ColPali-Vespa Visual Retrieval System${NC}"
echo "================================================"

# Setup logs directory
mkdir -p logs

# Detect virtual environment
if [ -d "venv" ]; then
    VENV_DIR="venv"
elif [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "env" ]; then
    VENV_DIR="env"
else
    echo -e "${RED}Error: No virtual environment found (venv, .venv, or env)${NC}"
    exit 1
fi

echo -e "Using virtual environment: ${YELLOW}$VENV_DIR${NC}"

# Pre-flight checks
echo ""
echo "Running pre-flight checks..."

# Check Vespa
if curl -s --max-time 5 http://localhost:8080/state/v1/health > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Vespa is running"
else
    echo -e "  ${RED}✗${NC} Vespa not reachable. Run: docker-compose up -d"
    exit 1
fi

# Check backend port
if lsof -i :7860 > /dev/null 2>&1; then
    echo -e "  ${YELLOW}!${NC} Port 7860 already in use (backend may be running)"
    SKIP_BACKEND=true
else
    echo -e "  ${GREEN}✓${NC} Port 7860 available"
    SKIP_BACKEND=false
fi

# Check frontend port
if lsof -i :3000 > /dev/null 2>&1; then
    echo -e "  ${YELLOW}!${NC} Port 3000 already in use (frontend may be running)"
    SKIP_FRONTEND=true
else
    echo -e "  ${GREEN}✓${NC} Port 3000 available"
    SKIP_FRONTEND=false
fi

# Check node_modules
if [ ! -d "web/node_modules" ]; then
    echo -e "  ${YELLOW}!${NC} Installing frontend dependencies..."
    (cd web && npm install)
fi
echo -e "  ${GREEN}✓${NC} Frontend dependencies installed"

echo ""

# Start backend
if [ "$SKIP_BACKEND" = false ]; then
    echo "Starting backend server..."
    source "$VENV_DIR/bin/activate"
    nohup python main.py >> logs/server.log 2>&1 &
    echo $! > logs/server.pid
    echo -e "  ${GREEN}✓${NC} Backend started (PID: $(cat logs/server.pid))"
else
    echo -e "  ${YELLOW}Skipped${NC} backend (already running)"
fi

# Start frontend
if [ "$SKIP_FRONTEND" = false ]; then
    echo "Starting frontend..."
    cd web
    nohup npm run dev >> "$PROJECT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$PROJECT_DIR/logs/frontend.pid"
    cd "$PROJECT_DIR"
    echo -e "  ${GREEN}✓${NC} Frontend started (PID: $(cat logs/frontend.pid))"
else
    echo -e "  ${YELLOW}Skipped${NC} frontend (already running)"
fi

# Wait for startup
sleep 2

echo ""
echo "================================================"
echo -e "${GREEN}System started!${NC}"
echo ""
echo "  Backend API:  http://localhost:7860"
echo "  Frontend:     http://localhost:3000"
echo ""
echo "Logs:"
echo "  tail -f logs/server.log    # Backend"
echo "  tail -f logs/frontend.log  # Frontend"
echo ""
echo "To stop:"
echo "  ./scripts/stop.sh"
echo "  # or manually: kill \$(cat logs/server.pid) \$(cat logs/frontend.pid)"
