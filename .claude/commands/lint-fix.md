---
description: Run ruff with auto-fix to automatically correct lint issues
---

## User Input

```text
$ARGUMENTS
```

## Outline

Run ruff linter with automatic fix mode to correct code quality and style issues. All output logged to `logs/lint-fix.log`.

1. **Setup logging (truncate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/lint-fix.log
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
   - If `$ARGUMENTS` contains specific paths, fix only those paths
   - If empty, fix the entire project (excluding venv)
   - Common usage examples:
     - `/lint-fix` - Fix all auto-fixable issues in project
     - `/lint-fix backend/` - Fix only backend directory
     - `/lint-fix main.py` - Fix specific file
     - `/lint-fix --unsafe-fixes` - Include unsafe fixes (be careful!)

4. **Execute ruff with fix mode (output to log only)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff check --fix --show-fixes --exclude venv $ARGUMENTS . > logs/lint-fix.log 2>&1
   ```

   If `$ARGUMENTS` already contains paths, omit the trailing `.`:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff check --fix --show-fixes --exclude venv $ARGUMENTS > logs/lint-fix.log 2>&1
   ```

5. **Also run ruff format**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff format --exclude venv $ARGUMENTS . >> logs/lint-fix.log 2>&1
   ```

5. **Read the log file to check results**:
   - Use the Read tool to read `logs/lint-fix.log`
   - This preserves context window - full output is in log, not conversation

6. **Report changes from log**:
   - List each file modified
   - Show what was changed in each file
   - If unfixable issues remain, list them from log

7. **Safety notes**:
   - By default, only safe fixes are applied
   - `--unsafe-fixes` may change code behavior - review changes carefully
   - **Always run `/test` after applying fixes** to ensure nothing broke
