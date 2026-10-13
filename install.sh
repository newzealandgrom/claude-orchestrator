#!/usr/bin/env bash
# Manual installer for Team Orchestrator (alternative to `/plugin install`).
#
#   ./install.sh                     # skill + agents for your user (~/.claude)
#   ./install.sh --project <dir>     # skill + agents for one project (<dir>/.claude)
#   ./install.sh --statusline        # also enable the limits-aware status line (user settings)
#   ./install.sh --hooks             # also register the limits/checkpoint hooks (not needed for plugin installs)
#   ./install.sh --statusline-only   # plugin users: only set up the status line
#   ./install.sh --dry-run           # show what would change
#
# settings.json is backed up to settings.json.bak-<timestamp> before any change.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
TARGET="$CONFIG"; SCOPE=user; STATUSLINE=0; HOOKS=0; ONLY_SL=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --project) TARGET="$(cd "$2" && pwd)/.claude"; SCOPE=project; shift 2;;
    --statusline) STATUSLINE=1; shift;;
    --hooks) HOOKS=1; shift;;
    --statusline-only) STATUSLINE=1; ONLY_SL=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n 2,12p "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 2; }
run() { if [ $DRY -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

SKILL_DST="$TARGET/skills/team-orchestrator"
STABLE="$CONFIG/team-orchestrator"            # stable copy of scripts for status line / hooks
if [ $ONLY_SL -eq 0 ]; then
  run mkdir -p "$TARGET/skills" "$TARGET/agents"
  run rm -rf "$SKILL_DST"
  run cp -R "$HERE/skills/team-orchestrator" "$SKILL_DST"
  for f in "$HERE"/agents/orch-*.md; do run cp "$f" "$TARGET/agents/"; done
  echo "installed skill -> $SKILL_DST, agents -> $TARGET/agents ($SCOPE scope)"
fi
run mkdir -p "$STABLE"
for f in limits.py statusline.py checkpoint.py; do run cp "$HERE/skills/team-orchestrator/scripts/$f" "$STABLE/$f"; done

if [ $STATUSLINE -eq 1 ] || [ $HOOKS -eq 1 ]; then
  SETTINGS="$CONFIG/settings.json"; [ "$SCOPE" = project ] && SETTINGS="$TARGET/settings.json"
  [ $DRY -eq 1 ] && { echo "[dry-run] would patch $SETTINGS (statusline=$STATUSLINE hooks=$HOOKS)"; exit 0; }
  python3 - "$SETTINGS" "$STABLE" "$STATUSLINE" "$HOOKS" <<'PY'
import json, os, shutil, sys, time
path, stable, want_sl, want_hooks = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4] == "1"
data = {}
if os.path.exists(path):
    shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
q = lambda p: '"' + p.replace('"', '\\"') + '"'
if want_sl:
    cmd = f"python3 {q(os.path.join(stable, 'statusline.py'))}"
    old = (data.get("statusLine") or {}).get("command")
    if old and "team-orchestrator" not in old:
        cmd = f"ORCH_STATUSLINE_NEXT={json.dumps(old)} {cmd}"   # keep the previous status line, appended
    data["statusLine"] = {"type": "command", "command": cmd}
if want_hooks:
    hooks = data.setdefault("hooks", {})
    def add(event, matcher, command):
        groups = hooks.setdefault(event, [])
        if any("team-orchestrator" in h.get("command", "") for g in groups for h in g.get("hooks", [])):
            return
        g = {"hooks": [{"type": "command", "command": command, "timeout": 30}]}
        if matcher:
            g["matcher"] = matcher
        groups.append(g)
    add("SessionStart", "compact|resume|clear", f"python3 {q(os.path.join(stable, 'checkpoint.py'))} --hook")
    add("PostToolUse", "Agent", f"python3 {q(os.path.join(stable, 'limits.py'))} --hook PostToolUse")
    add("UserPromptSubmit", None, f"python3 {q(os.path.join(stable, 'limits.py'))} --hook UserPromptSubmit --cache-sec 120")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
print(f"patched {path} (statusline={want_sl}, hooks={want_hooks}); backup kept next to it")
PY
fi
echo "done. Check: python3 \"$STABLE/limits.py\"   •   in Claude Code: /team-orchestrator <task>"
