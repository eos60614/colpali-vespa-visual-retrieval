---
description: Search branches for existing fixes and apply them to current branch
---

## User Input

```text
$ARGUMENTS
```

## Outline

Search through git branches to find if an issue was already solved elsewhere (from merged worktrees), then apply that fix to the current branch. All output logged to `logs/debug.log`.

1. **Setup logging (truncate to prevent bloat)**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/debug.log
   ```

2. **Detect available virtual environments**:
   Check for available venvs in order of preference:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && ls -d venv .venv env 2>/dev/null
   ```

   Log which venv will be used:
   ```bash
   echo "Available venvs:" >> logs/debug.log
   ls -d venv .venv env 2>/dev/null >> logs/debug.log || echo "None found" >> logs/debug.log
   ```

   Activate before running any Python commands:
   ```bash
   source /home/nirav60614/projects/colpali-vespa-visual-retrieval/venv/bin/activate
   ```

2. **Parse the problem description**:
   - `$ARGUMENTS` should describe the error, issue, or feature to search for
   - Extract key terms: error messages, function names, file names, concepts
   - Examples:
     - `/debug ImportError in colpali.py`
     - `/debug vespa connection timeout`
     - `/debug file upload validation`

3. **Get current branch context**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git branch --show-current > logs/debug.log 2>&1
   ```

4. **List all branches (local and remote)**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git branch -a >> logs/debug.log 2>&1
   ```

5. **Search commit messages across all branches for related fixes**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git log --all --oneline --grep="<keyword>" >> logs/debug.log 2>&1
   ```

   Search for multiple keywords extracted from `$ARGUMENTS`:
   - Error type (e.g., "ImportError", "TypeError", "timeout")
   - File names mentioned
   - Function/class names
   - Feature keywords (e.g., "upload", "ingest", "validation")

6. **Search commit diffs for code changes related to the issue**:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git log --all -p -S "<search_term>" --oneline >> logs/debug.log 2>&1
   ```

7. **Read the log file to analyze findings**:
   - Use the Read tool to read `logs/debug.log`
   - Identify commits that look like fixes for the described issue
   - Note which branch each commit is on

8. **Compare branches to find divergent fixes**:
   For each promising branch found:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git log --oneline HEAD..<branch_name> >> logs/debug.log 2>&1
   ```

   Show what commits exist in other branch but not current:
   ```bash
   cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git diff HEAD...<branch_name> -- <relevant_files> >> logs/debug.log 2>&1
   ```

9. **If fix found - present options to user**:
   - Show the commit(s) that contain the fix
   - Show the diff of what would change
   - Ask user to confirm before applying

10. **Apply the fix (with user confirmation)**:

    Option A - Cherry-pick specific commit:
    ```bash
    cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git cherry-pick <commit_hash>
    ```

    Option B - Apply specific file changes:
    ```bash
    cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git checkout <branch_name> -- <file_path>
    ```

    Option C - Merge entire branch:
    ```bash
    cd /home/nirav60614/projects/colpali-vespa-visual-retrieval && git merge <branch_name>
    ```

11. **Verify the fix**:
    - Run `/test` to ensure fix works and doesn't break anything
    - If cherry-pick has conflicts, help resolve them

12. **On no fix found**:
    - Report which branches were searched
    - Report what search terms were used
    - Suggest the issue may need a new fix
    - Offer to help debug the issue directly

## Search Strategy

When searching for fixes, prioritize:
1. **Commit messages** containing: "fix", "resolve", "bug", "error", error codes
2. **File changes** to files mentioned in the error
3. **Recent commits** on feature branches (001-*, 002-*, etc.)
4. **Branches with similar names** to the issue description
