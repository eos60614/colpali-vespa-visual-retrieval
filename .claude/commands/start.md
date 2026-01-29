---
description: Start the entire system (backend + frontend) at once
---

## User Input

```text
$ARGUMENTS
```

## Outline

Start both the **backend API server** (port 7860) and **frontend Next.js** (port 3000) in the background. All output logged to separate log files with active monitoring.

1. **Setup logging (rotate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   # Rotate backend log
   tail -1000 /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log 2>/dev/null > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log.prev || true
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log
   # Rotate frontend log
   tail -1000 /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/frontend.log 2>/dev/null > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/frontend.log.prev || true
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/frontend.log
   ```

2. **Detect and activate virtual environment**:
   Check for available venvs in order of preference:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && ls -d venv .venv env 2>/dev/null | head -1
   ```

   Activate before running backend commands:
   ```bash
   source /home/nirav60614/projects/colpali-vespa-visual-retrieval/venv/bin/activate
   ```

3. **Parse arguments** (if provided):
   - `--backend-only` - Only start the backend server
   - `--frontend-only` - Only start the frontend
   - `--reload` or `-r` - Enable hot reload for backend
   - Common usage examples:
     - `/start` - Start both backend and frontend
     - `/start --reload` - Start both with backend hot reload
     - `/start --backend-only` - Start only the backend
     - `/start --frontend-only` - Start only the frontend

4. **Pre-flight checks (STOP on any failure)**:
   - Verify Vespa is accessible:
     ```bash
     curl -s --max-time 5 http://localhost:8080/state/v1/health || echo "VESPA NOT REACHABLE"
     ```
   - Check if backend port is already in use:
     ```bash
     lsof -i :7860 2>/dev/null && echo "PORT 7860 IN USE"
     ```
   - Check if frontend port is already in use:
     ```bash
     lsof -i :3000 2>/dev/null && echo "PORT 3000 IN USE"
     ```
   - Check frontend dependencies exist:
     ```bash
     [ -d /home/nirav60614/projects/colpali-vespa-visual-retrieval/web/node_modules ] || echo "RUN npm install in web/"
     ```
   - **If any pre-flight fails, STOP and report the error**

5. **Start the backend server in BACKGROUND**:

   Default (no hot reload):
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && nohup python main.py >> logs/server.log 2>&1 &
   echo $! > logs/server.pid
   ```

   With hot reload:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && nohup uvicorn main:app --host 0.0.0.0 --port 7860 --reload >> logs/server.log 2>&1 &
   echo $! > logs/server.pid
   ```

6. **Start the frontend in BACKGROUND**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval/web && nohup npm run dev >> ../logs/frontend.log 2>&1 &
   echo $! > ../logs/frontend.pid
   ```

7. **Wait briefly for both to start**:
   ```bash
   sleep 3
   ```

8. **Verify both processes are running**:
   ```bash
   ps -p $(cat /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.pid) > /dev/null 2>&1 && echo "Backend running" || echo "Backend FAILED"
   ps -p $(cat /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/frontend.pid) > /dev/null 2>&1 && echo "Frontend running" || echo "Frontend FAILED"
   ```

9. **Read the log files to verify startup**:
   - Use the Read tool to read `logs/server.log` (check for backend startup)
   - Use the Read tool to read `logs/frontend.log` (check for frontend startup)
   - This preserves context window - full output is in logs, not conversation

10. **Report startup info**:
    - Display the URLs:
      - Backend API: http://localhost:7860
      - Frontend: http://localhost:3000
    - Show PIDs from log files
    - Note: "System running in background"
    - To monitor logs:
      - `tail -f logs/server.log` (backend)
      - `tail -f logs/frontend.log` (frontend)
    - To stop system:
      - `kill $(cat logs/server.pid) $(cat logs/frontend.pid)`

11. **On startup failure - STOP and investigate**:
    - Read the relevant log file to understand the error
    - Common issues:
      - Vespa not reachable: "Run `docker-compose up -d`"
      - Port in use: "Kill existing process or use different port"
      - Import errors: "Check virtual environment activation"
      - Missing node_modules: "Run `cd web && npm install`"
