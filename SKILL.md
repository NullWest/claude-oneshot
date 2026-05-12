---
name: oneshot-rate
description: Analyze Claude Code one-shot edit rate per model from session JSONL files
triggers:
  - "one-shot"
  - "oneshot"
  - "one shot rate"
  - "edit success rate"
  - "model efficiency"
  - "model comparison"
argument-hint: "[days]"
---

# One-Shot Rate Analysis

Analyze your Claude Code one-shot edit rate per model by parsing session JSONL files.

## Definitions

- **Turn**: A user prompt followed by all assistant responses before the next user prompt
- **Edit turn**: A turn where Claude used any edit tool (Edit, Write, FileEditTool, FileWriteTool, NotebookEdit)
- **Retry**: An edit→bash→edit cycle within a single turn (Claude edited, ran bash to test, then edited again to fix)
- **One-shot**: An edit turn with zero retries — Claude's edits landed without self-correction

## Workflow

Write and run a single Python script that produces three report sections:

### Section 1: Per-Model One-Shot Rate

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
5. Per model, compute: editTurns, oneShotTurns, oneShotRate = oneShotTurns / editTurns

If a `[days]` argument is provided, only include sessions from the last N days. Otherwise include all sessions.

The script output should be **GitHub-flavored markdown** so it renders nicely in the chat message. Use markdown tables, headers, and bullet points.

### Section 2: Category Breakdown

Classify each edit turn into a category based on tools used and user message keywords:
- **coding**: has edit tools (default for edit turns)
- **feature**: user message matches feature keywords (add, implement, create, build, new)
- **debugging**: user message matches debug keywords (fix, bug, error, broken, failing, debug)
- **refactoring**: user message matches refactor keywords (refactor, rename, move, extract, clean up)
- **testing**: user message matches test keywords (test, spec, coverage)

Apply category refinement: check keywords first, fall back to "coding" for generic edit turns.

Per model + category, show one-shot rate. Skip combinations with 0 edit turns.

### Section 3: Weekly Trend

Group edit turns by ISO week (YYYY-Wnn) using the timestamp from the first assistant message in the turn. Per week, compute overall one-shot rate and per-model rates. Only show weeks with at least 1 edit turn. Show model columns dynamically.

### Section 4: Summary

Compute and print 2-3 bullet points:
- Best and worst model/category combo
- Biggest week-over-week change in overall rate
- Model with highest vs lowest one-shot rate and the gap between them

### Output format

The entire script output should be markdown. After the script runs, echo its output directly as your message (do not wrap it in a code block or add commentary). Example output:

```
## One-Shot Rate by Model

| Model | Edit Turns | One-Shot | Rate |
|---|---:|---:|---:|
| claude-opus-4-7 | 328 | 247 | **75.3%** |
| claude-opus-4-6 | 197 | 189 | **95.9%** |
| **TOTAL** | **525** | **436** | **83.0%** |

## Category Breakdown

| Model | Category | Edits | 1-Shot | Rate |
|---|---|---:|---:|---:|
| claude-opus-4-7 | coding | 210 | 165 | 78.6% |
| claude-opus-4-7 | feature | 58 | 38 | 65.5% |
| claude-opus-4-6 | coding | 150 | 145 | 96.7% |

## Weekly Trend

| Week | Overall | opus-4-6 | opus-4-7 |
|---|---:|---:|---:|
| 2026-W15 | 88.2% | 85.0% (20) | - |
| 2026-W16 | 79.3% | 97.0% (173) | 84.0% (37) |

## Summary

- **Best combo:** opus-4-6 testing 100.0% (4/4) — **Worst:** opus-4-7 testing 71.4% (5/7)
- **Biggest weekly swing:** W16→W17 -19.6pp (94.8% → 75.2%)
- **Model gap:** opus-4-6 96.0% vs opus-4-7 75.3% (20.7pp)
```

After running the script, print its stdout directly as your response text. Do not add any additional commentary.

## Notes

- This replicates the per-model one-shot metric from codeburn
- The key gotcha is that Claude Code JSONL stores tool results as `type: "user"` messages — you must check content for `tool_result` blocks to avoid splitting turns at every tool call
- EDIT_TOOLS = {Edit, Write, FileEditTool, FileWriteTool, NotebookEdit}
- BASH_TOOLS = {Bash, BashTool, PowerShellTool}
