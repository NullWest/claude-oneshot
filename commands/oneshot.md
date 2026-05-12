---
description: "Show one-shot edit rate per model from Claude Code session data"
argument-hint: "[days]"
---

Write and run a single Python script that analyzes Claude Code session JSONL files and prints GitHub-flavored markdown output. If "$ARGUMENTS" contains a number, use it as a days filter (only include sessions from the last N days). Otherwise include all sessions.

## Definitions

- **Turn**: A user prompt followed by all assistant responses before the next user prompt
- **Edit turn**: A turn where Claude used any edit tool (Edit, Write, FileEditTool, FileWriteTool, NotebookEdit)
- **Retry**: An edit→bash→edit cycle within a single turn (Claude edited, ran bash to test, then edited again to fix)
- **One-shot**: An edit turn with zero retries — Claude's edits landed without self-correction

## Script requirements

1. Read all `.jsonl` session files from `~/.claude/projects/`
2. Group messages into turns. **Critical**: tool_result messages have `type: "user"` in the JSONL — filter these out by checking for `tool_result` content blocks. Only split turns on real user messages (those with `text` content or plain string content).
3. For each turn, determine:
   - **hasEdits**: did any assistant message use Edit, Write, FileEditTool, FileWriteTool, or NotebookEdit?
   - **model**: the `message.model` field from the first assistant message (skip `<synthetic>`)
   - **retries**: count edit→bash→edit cycles:
     ```
     saw_edit = False
     saw_bash_after_edit = False
     retries = 0
     for each assistant message:
       has_edit = uses Edit/Write/FileEditTool/FileWriteTool/NotebookEdit
       has_bash = uses Bash/BashTool/PowerShellTool
       if has_edit:
         if saw_bash_after_edit: retries++
         saw_edit = True
         saw_bash_after_edit = False
       if has_bash and saw_edit:
         saw_bash_after_edit = True
     ```
4. A turn is "one-shot" if `hasEdits == True` and `retries == 0`
5. Classify each edit turn by user message keywords: debugging (fix/bug/error/broken/failing/debug), refactoring (refactor/rename/move/extract/clean up), testing (test/spec/coverage), feature (add/implement/create/build/new), default to coding.

## Output format (GitHub-flavored markdown)

The script must print four sections as markdown tables:

### Section 1: One-Shot Rate by Model
Markdown table with columns: Model, Edit Turns, One-Shot, Rate (bold). Include a TOTAL row.

### Section 2: Category Breakdown
Markdown table with columns: Model (short name), Category, Edits, 1-Shot, Rate. Sorted by model edit count desc, then category edit count desc.

### Section 3: Weekly Trend
Group by ISO week. Markdown table with columns: Week, Overall, then one column per model (dynamic). Show rate and edit count like `85% (20)`.

### Section 4: Summary
Compute programmatically as bullet points:
- Best and worst model/category combo with rates
- Biggest week-over-week change in overall rate
- Model with highest vs lowest one-shot rate and the gap

## After running

Print the script's stdout directly as your response. Do not add any additional commentary.
