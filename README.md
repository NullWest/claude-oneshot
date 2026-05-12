# claude-oneshot

Measure your Claude Code **one-shot edit rate** per model.

A "one-shot" edit is when Claude's code changes land without needing to self-correct — no edit→bash→edit retry cycle within the same turn.

## What it measures

| Term | Definition |
|---|---|
| **Turn** | A user prompt + all assistant responses before the next prompt |
| **Edit turn** | A turn where Claude used Edit, Write, or similar tools |
| **Retry** | An edit→bash→edit cycle (Claude edited, tested, then fixed its own work) |
| **One-shot** | An edit turn with zero retries |

## Usage

```bash
# all sessions
python oneshot.py

# last 30 days
python oneshot.py 30

# markdown output (for Claude Code skill integration)
python oneshot.py --markdown
python oneshot.py 30 --markdown
```

## Output

Four sections:

1. **Per-model one-shot rate** — which models land edits cleanly
2. **Category breakdown** — one-shot rate by task type (coding, debugging, feature, refactoring, testing)
3. **Weekly trend** — how your rate changes over time
4. **Summary** — auto-detected insights (best/worst combos, biggest swings, model gaps)

### Example

```
Model                               Edit Turns   One-Shot     Rate
-------------------------------------------------------------------
claude-opus-4-7                            328        247    75.3%
claude-opus-4-6                            197        189    95.9%
-------------------------------------------------------------------
TOTAL                                      525        436    83.0%
```

## As a Claude Code skill

Copy the `SKILL.md` file to `~/.claude/skills/omc-learned/oneshot-rate/SKILL.md` to use it as an [oh-my-claudecode](https://github.com/anthropics/oh-my-claudecode) skill. Then just say "show me my one-shot rate" in any session.

## How it works

Claude Code stores session transcripts as JSONL files in `~/.claude/projects/`. Each line is a message with tool calls. The script:

1. Parses all session JSONL files
2. Groups messages into turns (filtering out `tool_result` messages that masquerade as user messages)
3. Detects edit→bash→edit retry cycles per turn
4. Attributes each turn to the primary model used
5. Computes one-shot rate = edit turns with zero retries / total edit turns

This replicates the per-model one-shot metric from [codeburn](https://www.npmjs.com/package/codeburn).

## Requirements

- Python 3.8+
- Claude Code session data in `~/.claude/projects/`
