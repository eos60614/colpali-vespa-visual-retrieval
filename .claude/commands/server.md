---
description: Start the backend API server with optional hot reload
---

## User Input

```text
$ARGUMENTS
```

## Outline

Start the Starlette/Uvicorn API server **in the background** for the colpali-vespa application. All output logged to `logs/server.log` with active monitoring.

1. **Setup logging (rotate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   # Keep last 1000 lines from previous run, then start fresh
   tail -1000 /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log 2>/dev/null > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log.prev || true
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/server.log
   ```

2. **Detect and activate virtual environment**:
   Check for available venvs in order of preference:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && ls -d venv .venv env 2>/dev/null | head -1
   ```

   Activate before running commands:
   ```bash
   source /home/nirav60614/projects/colpali-vespa-visual-retrieval/venv/bin/activate
   ```

2. **Parse arguments** (if provided):
   - `--reload` or `-r` - Enable hot reload for development
   - `--port <num>` - Use custom port (default: 7860)
   - `--fg` or `--foreground` - Run in foreground instead of background
   - Common usage examples:
     - `/server` - Start server in background on port 7860
     - `/server --reload` - Start with hot reload enabled (background)
     - `/server --fg` - Run in foreground (blocking)

3. **Pre-flight checks (STOP on any failure)**:
   - Verify Vespa is accessible:
     ```bash
     curl -s --max-time 5 http://localhost:8080/state/v1/health || echo "VESPA NOT REACHABLE"
     ```
   - Check if port is already in use:
     ```bash
     lsof -i :7860 2>/dev/null && echo "PORT 7860 IN USE"
     ```
   - **If any pre-flight fails, STOP and report the error**

5. **Start the server in BACKGROUND with logging**:

   Default (background, no hot reload):
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && nohup python main.py >> logs/server.log 2>&1 &
   echo $! > logs/server.pid
   ```

   With hot reload (background):
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && nohup uvicorn main:app --host 0.0.0.0 --port 7860 --reload >> logs/server.log 2>&1 &
   echo $! > logs/server.pid
   ```

5. **Monitor the log file for startup**:
   - Wait briefly for server to start:
     ```bash
     sleep 2
     ```
   - Check if process is still running:
     ```bash
     ps -p $(cat logs/server.pid) > /dev/null 2>&1 && echo "Server running" || echo "Server FAILED to start"
     ```

6. **Read the log file to verify startup**:
   - Use the Read tool to read `logs/server.log`
   - This preserves context window - full output is in log, not conversation
   - Check for startup success or errors

7. **Report startup info**:
   - Display the URL to access the app (http://localhost:7860)
   - Show PID from `logs/server.pid`
   - Note: "Server running in background"
   - To monitor logs: `tail -f logs/server.log`
   - To stop server: `kill $(cat logs/server.pid)`

8. **On startup failure - STOP and investigate**:
   - Read the full log file to understand the error
   - Common issues:
     - Connection refused: "Vespa not running - run `docker-compose up -d`"
     - Port in use: "Kill process on port 7860 or use different port"
     - Import errors: "Check virtual environment activation"
