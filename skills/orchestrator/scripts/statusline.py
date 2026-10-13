#!/usr/bin/env python3
"""Claude Code status line for Claude Orchestrator.

Claude Code pipes a JSON document to the status line command on every refresh. For Pro/Max
subscribers it contains the official plan usage (``rate_limits.five_hour`` / ``seven_day``:
``used_percentage`` and ``resets_at``) and, for everyone, ``context_window.used_percentage``.

This script
  1. prints one compact line:  Opus 5.5 · ctx 41% · 5h 63% ↻14:50 · 7d 22%
  2. saves the official numbers to <config>/claude-orchestrator/statusline.json, where
     ``limits.py`` picks them up (exact data beats estimates from transcripts).

Enable it in ~/.claude/settings.json (or a project's .claude/settings.json):
    "statusLine": {"type": "command", "command": "python3 /ABS/PATH/statusline.py"}
To keep another status line, set ORCH_STATUSLINE_NEXT to its command: its output is appended.
Standard library only; never prints secrets.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile


def config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def snapshot_path() -> str:
    return os.path.join(config_dir(), "claude-orchestrator", "statusline.json")


def pct(v) -> str:
    try:
        return f"{float(v):.0f}%"
    except (TypeError, ValueError):
        return "?"


def reset_hint(epoch) -> str:
    try:
        return "↻" + dt.datetime.fromtimestamp(float(epoch)).strftime("%H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def save_snapshot(data: dict) -> None:
    keep = {
        "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "session_id": data.get("session_id"),
        "transcript_path": data.get("transcript_path"),
        "model": (data.get("model") or {}).get("id") if isinstance(data.get("model"), dict) else data.get("model"),
        "context_window": data.get("context_window"),
        "rate_limits": data.get("rate_limits"),
        "effort": data.get("effort"),
    }
    path = snapshot_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".statusline.")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(keep, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    save_snapshot(data)

    model = data.get("model") or {}
    name = model.get("display_name") or model.get("id") or "Claude" if isinstance(model, dict) else str(model)
    parts = [name]
    ctx = data.get("context_window") or {}
    if ctx.get("used_percentage") is not None:
        parts.append(f"ctx {pct(ctx.get('used_percentage'))}")
    rl = data.get("rate_limits") or {}
    five, week = rl.get("five_hour") or {}, rl.get("seven_day") or {}
    if five.get("used_percentage") is not None:
        parts.append(f"5h {pct(five.get('used_percentage'))} {reset_hint(five.get('resets_at'))}".strip())
    if week.get("used_percentage") is not None:
        parts.append(f"7d {pct(week.get('used_percentage'))}")
    line = " · ".join(parts)

    nxt = os.environ.get("ORCH_STATUSLINE_NEXT")
    if nxt:
        try:
            extra = subprocess.run(nxt, shell=True, input=raw, capture_output=True, text=True, timeout=5).stdout.strip()
            if extra:
                line = f"{line} | {extra}"
        except (OSError, subprocess.SubprocessError):
            pass
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
