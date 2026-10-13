#!/usr/bin/env python3
"""Add or remove Claude Orchestrator's status line and hooks in a Claude Code settings.json.

    patch_settings.py install   <settings.json> <stable-dir> <statusline 0|1> <hooks 0|1>
    patch_settings.py uninstall <settings.json>

The file is backed up to <settings.json>.bak-<timestamp> first. Only entries that point to
Claude Orchestrator (or its v1 name, team-orchestrator) are touched; a status line that existed
before install is kept (appended via ORCH_STATUSLINE_NEXT) and restored on uninstall.
Standard library only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

OURS, LEGACY = "claude-orchestrator", "team-orchestrator"
NEXT_RE = re.compile(r'^ORCH_STATUSLINE_NEXT=("(?:[^"\\]|\\.)*")\s')


def q(path: str) -> str:
    return '"' + path.replace('"', '\\"') + '"'


def is_ours(cmd: str) -> bool:
    return OURS in cmd or LEGACY in cmd


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def previous_statusline(cmd: str) -> str:
    """The user's own status line hidden behind ours, or the command itself if it is not ours."""
    m = NEXT_RE.match(cmd)
    if m:
        return json.loads(m.group(1))
    return "" if is_ours(cmd) else cmd


def drop_hooks(data: dict, marks) -> None:
    hooks = data.get("hooks") or {}
    for event, groups in list(hooks.items()):
        keep = [g for g in groups if not any(m in h.get("command", "") for h in g.get("hooks", []) for m in marks)]
        if keep:
            hooks[event] = keep
        else:
            hooks.pop(event)
    if "hooks" in data and not data["hooks"]:
        data.pop("hooks")


def has_legacy(data: dict):
    """(v1 status line present, v1 hooks present) — they are migrated even without explicit flags."""
    sl = LEGACY in ((data.get("statusLine") or {}).get("command") or "")
    hooks = any(LEGACY in h.get("command", "") for groups in (data.get("hooks") or {}).values()
                for g in groups for h in g.get("hooks", []))
    return sl, hooks


def install(path: str, stable: str, want_sl: bool, want_hooks: bool) -> None:
    data = load(path)
    legacy_sl, legacy_hooks = has_legacy(data)
    want_sl, want_hooks = want_sl or legacy_sl, want_hooks or legacy_hooks
    if want_sl:
        cmd = f"python3 {q(os.path.join(stable, 'statusline.py'))}"
        old = previous_statusline((data.get("statusLine") or {}).get("command") or "")
        if old:
            cmd = f"ORCH_STATUSLINE_NEXT={json.dumps(old)} {cmd}"
        data["statusLine"] = {"type": "command", "command": cmd}
    if want_hooks:
        drop_hooks(data, (LEGACY,))  # replace a v1 install
        hooks = data.setdefault("hooks", {})

        def add(event, matcher, script, args):
            groups = hooks.setdefault(event, [])
            for g in groups:  # already installed: only bring the matcher up to date
                if any(OURS in h.get("command", "") and script in h.get("command", "") for h in g.get("hooks", [])):
                    if matcher and g.get("matcher") != matcher:
                        g["matcher"] = matcher
                    return
            group = {"hooks": [{"type": "command", "command": f"python3 {q(os.path.join(stable, script))} {args}", "timeout": 30}]}
            if matcher:
                group["matcher"] = matcher
            groups.append(group)

        add("SessionStart", "compact|resume|clear", "checkpoint.py", "--hook")
        add("PostToolUse", "Agent|SendMessage", "limits.py", "--hook PostToolUse")
        add("PostToolUse", "Agent|SendMessage", "costs.py", "--hook PostToolUse")
        add("UserPromptSubmit", None, "limits.py", "--hook UserPromptSubmit --cache-sec 120")
        add("UserPromptSubmit", None, "costs.py", "--hook UserPromptSubmit")
    save(path, data)
    print(f"patched {path} (statusline={want_sl}, hooks={want_hooks}); backup kept next to it")


def uninstall(path: str) -> None:
    if not os.path.exists(path):
        return
    data = load(path)
    cmd = (data.get("statusLine") or {}).get("command") or ""
    if is_ours(cmd):
        old = previous_statusline(cmd)
        if old:
            data["statusLine"] = {"type": "command", "command": old}
        else:
            data.pop("statusLine")
    drop_hooks(data, (OURS, LEGACY))
    save(path, data)
    print(f"cleaned {path}; backup kept next to it")


def main(argv) -> int:
    if len(argv) >= 6 and argv[1] == "install":
        install(argv[2], argv[3], argv[4] == "1", argv[5] == "1")
        return 0
    if len(argv) >= 3 and argv[1] == "uninstall":
        uninstall(argv[2])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
