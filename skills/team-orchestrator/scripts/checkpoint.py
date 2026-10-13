#!/usr/bin/env python3
"""Re-inject the orchestrator's state after /compact, /clear or resume (SessionStart hook).

Finds the newest in-progress plan in <project>/.claude/plans/*.md (status line contains
"in-progress"), and prints its header plus the "Checkpoint" section, followed by a one-line
limits summary. Claude Code adds SessionStart hook output to the fresh context, so the
orchestrator continues from the plan instead of from a lossy summary.

    checkpoint.py                 # print checkpoint for $CLAUDE_PROJECT_DIR or cwd
    checkpoint.py --hook          # same, read hook JSON from stdin (cwd/source), JSON output
Standard library only.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

MAX_LINES = 80
STATUS_RE = re.compile(r"(status|статус)\s*[:*]*\s*\**\s*in[- ]progress", re.I)
SECTION_RE = re.compile(r"^##\s+(checkpoint|чекпоинт)", re.I)


def active_plan(project: str):
    plans = sorted(glob.glob(os.path.join(project, ".claude", "plans", "*.md")), key=os.path.getmtime, reverse=True)
    for path in plans:
        try:
            with open(path, encoding="utf-8") as fh:
                head = fh.read(4000)
        except OSError:
            continue
        if STATUS_RE.search(head):
            return path
    return None


def excerpt(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    header = lines[:12]
    section, inside = [], False
    for line in lines:
        if SECTION_RE.match(line):
            inside, section = True, [line]
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            section.append(line)
    body = header + ["..."] + (section[:MAX_LINES] if section else ["(no Checkpoint section yet)"])
    return "\n".join(body)


def limits_line() -> str:
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "limits.py")
    try:
        out = subprocess.run([sys.executable, script, "--hook", "plain", "--always", "--cache-sec", "120"],
                             capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL).stdout.strip()
        return out
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    hook = "--hook" in sys.argv
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    source = ""
    if hook and not sys.stdin.isatty():
        try:
            data = json.loads(sys.stdin.read() or "{}")
            project = data.get("cwd") or project
            source = data.get("source") or ""
        except ValueError:
            pass
    plan = active_plan(project)
    if not plan:
        return 0
    text = (f"[team-orchestrator] Session {source or 'start'}: an orchestration plan is in progress — "
            f"{os.path.relpath(plan, project)}. Continue from its Checkpoint; re-read the plan before acting.\n\n"
            + excerpt(plan))
    lim = limits_line()
    if lim:
        text += "\n\n" + lim
    if hook:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
