#!/usr/bin/env bash
# Remove a manual install of Team Orchestrator (plugin installs: `claude plugin uninstall team-orchestrator`).
#   ./uninstall.sh [--project <dir>]
# Removes the skill, the orch-* agents, the stable scripts copy, and status line / hooks entries that point to
# team-orchestrator (settings.json is backed up first). Your other settings are untouched.
set -euo pipefail
CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; TARGET="$CONFIG"; SETTINGS="$CONFIG/settings.json"
if [ "${1:-}" = "--project" ]; then TARGET="$(cd "$2" && pwd)/.claude"; SETTINGS="$TARGET/settings.json"; fi
rm -rf "$TARGET/skills/team-orchestrator"
rm -f "$TARGET"/agents/orch-*.md
rm -rf "$CONFIG/team-orchestrator"
if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" <<'PY'
import json, shutil, sys, time
path = sys.argv[1]
shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
data = json.load(open(path, encoding="utf-8"))
import re
sl = data.get("statusLine") or {}
cmd = sl.get("command", "")
if "team-orchestrator" in cmd:
    m = re.match(r'^ORCH_STATUSLINE_NEXT=("(?:[^"\\]|\\.)*")\s', cmd)
    if m:  # restore the status line that existed before install
        data["statusLine"] = {"type": "command", "command": json.loads(m.group(1))}
    else:
        data.pop("statusLine")
for event, groups in list((data.get("hooks") or {}).items()):
    keep = [g for g in groups if not any("team-orchestrator" in h.get("command", "") for h in g.get("hooks", []))]
    if keep:
        data["hooks"][event] = keep
    else:
        data["hooks"].pop(event)
if data.get("hooks") == {}:
    data.pop("hooks")
json.dump(data, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"cleaned {path}")
PY
fi
echo "Team Orchestrator removed from $TARGET"
