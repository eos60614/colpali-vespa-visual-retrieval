---
description: Run pytest test suite with optional filtering and verbosity options
---

## User Input

```text
$ARGUMENTS
```

## Outline

Run the project test suite using pytest. **Default behavior is verbose and fail-fast** - stop on first failure to tackle errors immediately. All output logged to `logs/test.log`.

1. **Setup logging (truncate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/test.log
   ```

2. **Detect and activate virtual environment**:
   Check for available venvs in order of preference:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && ls -d venv .venv env .env 2>/dev/null | head -1
   ```

   Use the first one found that has a bin/activate:
   - `venv/bin/activate`
   - `.venv/bin/activate`
   - `env/bin/activate`

   Activate before running commands:
   ```bash
   source /home/nirav60614/projects/colpali-vespa-visual-retrieval/venv/bin/activate
   ```

2. **Default flags** (always applied unless overridden):
   - `-v` - Verbose output to see exactly what's happening
   - `-x` - Stop on first failure - no point continuing with broken tests
   - `--tb=short` - Show concise tracebacks

3. **Parse arguments** (if provided):
   - Additional arguments are appended to defaults
   - Common usage examples:
     - `/test` - Run all tests (verbose, fail-fast)
     - `/test tests/unit` - Run only unit tests
     - `/test tests/integration` - Run only integration tests
     - `/test -k "test_ingest"` - Run tests matching pattern
     - `/test --tb=long` - Full tracebacks for debugging

5. **Execute pytest (output to log only)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && source venv/bin/activate && python -m pytest -v -x --tb=short $ARGUMENTS > logs/test.log 2>&1
   ```

5. **Read the log file to check results**:
   - Use the Read tool to read `logs/test.log`
   - Check exit status and parse test results from log
   - This preserves context window - full output is in log, not conversation

6. **On failure - STOP and investigate**:
   - Read the relevant portion of the log showing the failure
   - Identify the failing test file and line number
   - Show the assertion that failed or exception raised
   - Suggest specific fixes based on the error type

7. **On success**:
   - Report total tests passed (from log)
   - Show test duration for performance awareness
