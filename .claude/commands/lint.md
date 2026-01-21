---
description: Run ruff linter to check code quality and style issues
---

## User Input

```text
$ARGUMENTS
```

## Outline

Run ruff linter to check for code quality and style issues. **Shows all errors verbosely** - every issue gets attention. All output logged to `logs/lint.log`.

1. **Setup logging (truncate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/lint.log
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

2. **Default flags** (always applied):
   - `--output-format=full` - Show full context for each error
   - `--show-source` - Display the offending code
   - `--exclude venv` - Skip virtual environment

3. **Parse arguments** (if provided):
   - If `$ARGUMENTS` contains specific paths, lint only those paths
   - Common usage examples:
     - `/lint` - Lint entire project
     - `/lint backend/` - Lint only backend directory
     - `/lint main.py` - Lint specific file

5. **Execute ruff check (output to log only)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff check --output-format=full --show-source --exclude venv $ARGUMENTS . > logs/lint.log 2>&1
   ```

   If `$ARGUMENTS` already contains paths, omit the trailing `.`:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff check --output-format=full --show-source --exclude venv $ARGUMENTS > logs/lint.log 2>&1
   ```

5. **Read the log file to check results**:
   - Use the Read tool to read `logs/lint.log`
   - This preserves context window - full output is in log, not conversation

6. **On errors found - address each one**:
   - Read errors from log file
   - For each error, explain:
     - What the error means
     - Why it's problematic
     - How to fix it (or suggest `/lint-fix` for auto-fixable)
   - List errors that cannot be auto-fixed and require manual attention

7. **Exit codes matter**:
   - Exit 0 = No issues (success)
   - Exit 1 = Issues found (requires action)
   - Never ignore non-zero exit codes
