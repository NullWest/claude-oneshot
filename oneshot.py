#!/usr/bin/env python3
"""Analyze Claude Code one-shot edit rate per model from session JSONL files.

A "one-shot" edit is when Claude's code changes land without needing to
self-correct (no edit→bash→edit retry cycle within the same turn).

Usage:
    python oneshot.py [days]       # optional: limit to last N days
    python oneshot.py --markdown   # output as GitHub-flavored markdown tables
    python oneshot.py 30 --markdown
"""

import json
import glob
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

EDIT_TOOLS = {"Edit", "Write", "FileEditTool", "FileWriteTool", "NotebookEdit"}
BASH_TOOLS = {"Bash", "BashTool", "PowerShellTool"}

FEATURE_RE = re.compile(r"\b(add|implement|create|build|new)\b", re.I)
DEBUG_RE = re.compile(r"\b(fix|bug|error|broken|failing|debug)\b", re.I)
REFACTOR_RE = re.compile(r"\b(refactor|rename|move|extract|clean\s*up)\b", re.I)
TEST_RE = re.compile(r"\b(test|spec|coverage)\b", re.I)


def is_real_user_message(msg):
    """Filter out tool_result messages that masquerade as type 'user'."""
    content = msg.get("message", {}).get("content", [])
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        types = {b.get("type") for b in content if isinstance(b, dict)}
        if "tool_result" in types and "text" not in types:
            return False
        if "text" in types:
            return True
    return True


def get_tools(msg):
    content = msg.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return []
    return [
        b.get("name")
        for b in content
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name")
    ]


def get_model(msg):
    return msg.get("message", {}).get("model", "")


def get_timestamp(msg):
    return msg.get("timestamp", "")


def get_user_text(user_msg):
    if not user_msg:
        return ""
    content = user_msg.get("message", {}).get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def count_retries(assistant_msgs):
    """Count edit→bash→edit cycles within a turn.

    A retry is when Claude edits files, runs bash (presumably to test),
    then edits again — meaning it had to fix its own work.
    """
    saw_edit = False
    saw_bash_after_edit = False
    retries = 0
    for msg in assistant_msgs:
        tools = get_tools(msg)
        has_edit = any(t in EDIT_TOOLS for t in tools)
        has_bash = any(t in BASH_TOOLS for t in tools)
        if has_edit:
            if saw_bash_after_edit:
                retries += 1
            saw_edit = True
            saw_bash_after_edit = False
        if has_bash and saw_edit:
            saw_bash_after_edit = True
    return retries


def has_edits(msgs):
    return any(any(t in EDIT_TOOLS for t in get_tools(m)) for m in msgs)


def primary_model(msgs):
    for m in msgs:
        mod = get_model(m)
        if mod and mod != "<synthetic>":
            return mod
    return None


def first_timestamp(msgs):
    for m in msgs:
        ts = get_timestamp(m)
        if ts:
            return ts
    return ""


def classify(text):
    if DEBUG_RE.search(text):
        return "debugging"
    if REFACTOR_RE.search(text):
        return "refactoring"
    if TEST_RE.search(text):
        return "testing"
    if FEATURE_RE.search(text):
        return "feature"
    return "coding"


def iso_week(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
    except Exception:
        return None


def parse_timestamp(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def short_model(m):
    return m.replace("claude-", "").replace("-20251001", "")


def parse_sessions(days_limit=None):
    cutoff = None
    if days_limit:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_limit)

    session_dir = os.path.expanduser("~/.claude/projects")
    session_files = glob.glob(os.path.join(session_dir, "*", "*.jsonl"))

    all_turns = []
    for fp in session_files:
        try:
            with open(fp) as f:
                messages = [json.loads(line) for line in f if line.strip()]
        except Exception:
            continue

        turns = []
        current_assistants = []
        current_user = None
        for msg in messages:
            msg_type = msg.get("type")
            if msg_type == "user" and is_real_user_message(msg):
                if current_assistants:
                    turns.append((current_user, current_assistants))
                current_assistants = []
                current_user = msg
            elif msg_type == "assistant":
                current_assistants.append(msg)
        if current_assistants:
            turns.append((current_user, current_assistants))

        for user_msg, assistants in turns:
            if not has_edits(assistants):
                continue
            model = primary_model(assistants)
            if not model:
                continue
            ts = first_timestamp(assistants)
            if cutoff:
                dt = parse_timestamp(ts)
                if dt and dt < cutoff:
                    continue
            all_turns.append(
                {
                    "model": model,
                    "retries": count_retries(assistants),
                    "category": classify(get_user_text(user_msg)),
                    "week": iso_week(ts),
                }
            )
    return all_turns


def print_plain(all_turns):
    model_stats = defaultdict(lambda: {"e": 0, "o": 0})
    for t in all_turns:
        model_stats[t["model"]]["e"] += 1
        if t["retries"] == 0:
            model_stats[t["model"]]["o"] += 1
    te = sum(s["e"] for s in model_stats.values())
    to = sum(s["o"] for s in model_stats.values())

    print(f"{'Model':<35s} {'Edit Turns':>10s} {'One-Shot':>10s} {'Rate':>8s}")
    print("-" * 67)
    for model, s in sorted(model_stats.items(), key=lambda x: -x[1]["e"]):
        print(
            f"{model:<35s} {s['e']:>10d} {s['o']:>10d} {s['o']/s['e']*100:>7.1f}%"
        )
    print("-" * 67)
    print(f"{'TOTAL':<35s} {te:>10d} {to:>10d} {to/te*100:>7.1f}%")

    # Category breakdown
    cat_stats = defaultdict(lambda: {"e": 0, "o": 0})
    for t in all_turns:
        cat_stats[(t["model"], t["category"])]["e"] += 1
        if t["retries"] == 0:
            cat_stats[(t["model"], t["category"])]["o"] += 1

    print()
    print(f"{'Model':<25s} {'Category':<15s} {'Edits':>6s} {'1-Shot':>7s} {'Rate':>7s}")
    print("-" * 64)
    for (model, cat), s in sorted(
        cat_stats.items(),
        key=lambda x: (-model_stats[x[0][0]]["e"], -x[1]["e"]),
    ):
        print(
            f"{short_model(model):<25s} {cat:<15s} {s['e']:>6d} {s['o']:>7d} {s['o']/s['e']*100:>6.1f}%"
        )

    # Weekly trend
    week_stats = defaultdict(lambda: defaultdict(lambda: {"e": 0, "o": 0}))
    week_totals = defaultdict(lambda: {"e": 0, "o": 0})
    models_seen = set()
    for t in all_turns:
        w = t["week"]
        if not w:
            continue
        models_seen.add(t["model"])
        week_stats[w][t["model"]]["e"] += 1
        week_totals[w]["e"] += 1
        if t["retries"] == 0:
            week_stats[w][t["model"]]["o"] += 1
            week_totals[w]["o"] += 1

    ms = sorted(models_seen)
    print()
    header = f"{'Week':<12s} {'Overall':>8s}"
    for m in ms:
        header += f" {short_model(m):>12s}"
    print(header)
    print("-" * len(header))
    for week in sorted(week_totals.keys()):
        wt = week_totals[week]
        row = f"{week:<12s} {wt['o']/wt['e']*100:>7.1f}%"
        for m in ms:
            ws = week_stats[week][m]
            if ws["e"] > 0:
                r = f"{ws['o']/ws['e']*100:.0f}%({ws['e']})"
            else:
                r = "-"
            row += f" {r:>12s}"
        print(row)

    # Summary
    _print_summary(model_stats, cat_stats, week_totals, plain=True)


def print_markdown(all_turns):
    model_stats = defaultdict(lambda: {"e": 0, "o": 0})
    for t in all_turns:
        model_stats[t["model"]]["e"] += 1
        if t["retries"] == 0:
            model_stats[t["model"]]["o"] += 1
    te = sum(s["e"] for s in model_stats.values())
    to = sum(s["o"] for s in model_stats.values())

    print("## One-Shot Rate by Model\n")
    print("| Model | Edit Turns | One-Shot | Rate |")
    print("|---|---:|---:|---:|")
    for model, s in sorted(model_stats.items(), key=lambda x: -x[1]["e"]):
        print(
            f"| {model} | {s['e']} | {s['o']} | **{s['o']/s['e']*100:.1f}%** |"
        )
    print(f"| **TOTAL** | **{te}** | **{to}** | **{to/te*100:.1f}%** |")

    # Category breakdown
    cat_stats = defaultdict(lambda: {"e": 0, "o": 0})
    for t in all_turns:
        cat_stats[(t["model"], t["category"])]["e"] += 1
        if t["retries"] == 0:
            cat_stats[(t["model"], t["category"])]["o"] += 1

    print("\n## Category Breakdown\n")
    print("| Model | Category | Edits | 1-Shot | Rate |")
    print("|---|---|---:|---:|---:|")
    for (model, cat), s in sorted(
        cat_stats.items(),
        key=lambda x: (-model_stats[x[0][0]]["e"], -x[1]["e"]),
    ):
        print(
            f"| {short_model(model)} | {cat} | {s['e']} | {s['o']} | {s['o']/s['e']*100:.1f}% |"
        )

    # Weekly trend
    week_stats = defaultdict(lambda: defaultdict(lambda: {"e": 0, "o": 0}))
    week_totals = defaultdict(lambda: {"e": 0, "o": 0})
    models_seen = set()
    for t in all_turns:
        w = t["week"]
        if not w:
            continue
        models_seen.add(t["model"])
        week_stats[w][t["model"]]["e"] += 1
        week_totals[w]["e"] += 1
        if t["retries"] == 0:
            week_stats[w][t["model"]]["o"] += 1
            week_totals[w]["o"] += 1

    ms = sorted(models_seen)
    print("\n## Weekly Trend\n")
    print("| Week | Overall | " + " | ".join(short_model(m) for m in ms) + " |")
    print("|---|---:|" + "---:|" * len(ms))
    for week in sorted(week_totals.keys()):
        wt = week_totals[week]
        row = f"| {week} | {wt['o']/wt['e']*100:.1f}% |"
        for m in ms:
            ws = week_stats[week][m]
            if ws["e"] > 0:
                row += f" {ws['o']/ws['e']*100:.0f}% ({ws['e']}) |"
            else:
                row += " - |"
        print(row)

    # Summary
    _print_summary(model_stats, cat_stats, week_totals, plain=False)


def _print_summary(model_stats, cat_stats, week_totals, plain=True):
    prefix = "  " if plain else ""
    bullet = "•" if plain else "-"

    if plain:
        print(f"\nSummary:")
    else:
        print(f"\n## Summary\n")

    best = max(cat_stats.items(), key=lambda x: x[1]["o"] / x[1]["e"])
    worst = min(cat_stats.items(), key=lambda x: x[1]["o"] / x[1]["e"])
    best_r = best[1]["o"] / best[1]["e"] * 100
    worst_r = worst[1]["o"] / worst[1]["e"] * 100

    if plain:
        print(
            f"{prefix}{bullet} Best combo: {short_model(best[0][0])} {best[0][1]} {best_r:.1f}% ({best[1]['o']}/{best[1]['e']}) — Worst: {short_model(worst[0][0])} {worst[0][1]} {worst_r:.1f}% ({worst[1]['o']}/{worst[1]['e']})"
        )
    else:
        print(
            f"{bullet} **Best combo:** {short_model(best[0][0])} {best[0][1]} {best_r:.1f}% ({best[1]['o']}/{best[1]['e']}) — **Worst:** {short_model(worst[0][0])} {worst[0][1]} {worst_r:.1f}% ({worst[1]['o']}/{worst[1]['e']})"
        )

    sw = sorted(week_totals.keys())
    max_swing = 0
    swing_desc = ""
    for i in range(1, len(sw)):
        pr = week_totals[sw[i - 1]]["o"] / week_totals[sw[i - 1]]["e"] * 100
        cr = week_totals[sw[i]]["o"] / week_totals[sw[i]]["e"] * 100
        if abs(cr - pr) > max_swing:
            max_swing = abs(cr - pr)
            sign = "+" if cr > pr else "-"
            swing_desc = (
                f"{sw[i-1]}→{sw[i]} {sign}{max_swing:.1f}pp ({pr:.1f}% → {cr:.1f}%)"
            )
    if swing_desc:
        if plain:
            print(f"{prefix}{bullet} Biggest weekly swing: {swing_desc}")
        else:
            print(f"{bullet} **Biggest weekly swing:** {swing_desc}")

    mr = {m: s["o"] / s["e"] * 100 for m, s in model_stats.items()}
    if len(mr) >= 2:
        bm = max(mr, key=mr.get)
        wm = min(mr, key=mr.get)
        gap = mr[bm] - mr[wm]
        if plain:
            print(
                f"{prefix}{bullet} Model gap: {short_model(bm)} {mr[bm]:.1f}% vs {short_model(wm)} {mr[wm]:.1f}% ({gap:.1f}pp)"
            )
        else:
            print(
                f"{bullet} **Model gap:** {short_model(bm)} {mr[bm]:.1f}% vs {short_model(wm)} {mr[wm]:.1f}% ({gap:.1f}pp)"
            )


def main():
    args = sys.argv[1:]
    days = None
    markdown = False

    for arg in args:
        if arg == "--markdown":
            markdown = True
        elif arg.isdigit():
            days = int(arg)

    all_turns = parse_sessions(days_limit=days)

    if not all_turns:
        print("No edit turns found in session data.")
        sys.exit(1)

    if markdown:
        print_markdown(all_turns)
    else:
        print_plain(all_turns)


if __name__ == "__main__":
    main()
