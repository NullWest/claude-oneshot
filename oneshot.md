---
description: "Show one-shot edit rate per model from Claude Code session data"
---

Run `python3 ~/.claude/commands/oneshot.py $ARGUMENTS` and print its stdout directly as your response. Do not add commentary.

If no arguments are provided, run without arguments. Valid arguments: a number for days (e.g. `30`), `--markdown` for markdown tables, or both (e.g. `30 --markdown`).

Always pass `--markdown` even if the user didn't specify it — the output renders better in chat.
