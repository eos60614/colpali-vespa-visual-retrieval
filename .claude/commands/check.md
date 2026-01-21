---
description: Run full code quality check (lint + tests) before committing
---

## User Input

```text
$ARGUMENTS
```

## Outline

Run comprehensive code quality checks including linting and tests. **Fail-fast on any error** - stop immediately and address issues. All output logged to `logs/check.log`.

1. **Setup logging (truncate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/check.log
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

2. **Determine scope**:
   - If `$ARGUMENTS` is empty, run full checks on entire project
   - If `$ARGUMENTS` contains paths, focus checks on those paths
   - Common usage examples:
     - `/check` - Full project check
     - `/check backend/` - Check only backend
     - `/check --quick` - Skip slow integration tests

4. **Step 1: Run linting (output to log)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && ruff check --output-format=full --show-source --exclude venv . > logs/check.log 2>&1
   ```

4. **Read lint results from log**:
   - Use the Read tool to read `logs/check.log`
   - **If lint fails, STOP immediately**
   - Do NOT proceed to tests until lint passes
   - Suggest: "Run `/lint-fix` to auto-fix issues"

6. **Step 2: Run tests (only if lint passed)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && python -m pytest -v -x --tb=short tests/ >> logs/check.log 2>&1
   ```

   - `-x` flag stops on first failure
   - If `--quick` in `$ARGUMENTS`, skip integration tests:
     ```bash
     source venv/bin/activate && python -m pytest -v -x --tb=short tests/unit/ >> logs/check.log 2>&1
     ```

6. **Read test results from log**:
   - Use the Read tool to read `logs/check.log`
   - This preserves context window - full output is in log, not conversation

7. **On any failure**:
   - **STOP immediately** - do not continue to next step
   - Read error details from log
   - Explain what failed and why
   - Suggest specific fix

8. **On complete success only**:
   - Report "All checks passed - ready to commit"
