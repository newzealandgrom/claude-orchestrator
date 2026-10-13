#!/usr/bin/env bash
# Manual installer for Claude Orchestrator (alternative to the plugin install).
#
#   ./install.sh                     # skill + agents for your user (~/.claude)
#   ./install.sh --project <dir>     # skill + agents for one project (<dir>/.claude)
#   ./install.sh --statusline        # also enable the limits-aware status line (user settings)
#   ./install.sh --hooks             # also register the limits/budget/checkpoint hooks (not needed for plugin installs)
#   ./install.sh --statusline-only   # plugin users: only set up the status line
#   ./install.sh --dry-run           # show what would change
#
# settings.json is backed up to settings.json.bak-<timestamp> before any change.
# A v1 install ("team-orchestrator") is replaced: its skill folder is removed and its status line / hooks
# entries in settings.json are migrated to this version automatically.
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
    -h|--help) sed -n 2,13p "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
command -v python3 >/dev/null || { echo "python3 is required (macOS: xcode-select --install; Linux: your package manager)" >&2; exit 2; }
run() { if [ $DRY -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

SKILL_DST="$TARGET/skills/orchestrator"
STABLE="$CONFIG/claude-orchestrator"          # stable copy of scripts for status line / hooks
if [ $ONLY_SL -eq 0 ]; then
  run mkdir -p "$TARGET/skills" "$TARGET/agents"
  run rm -rf "$SKILL_DST" "$TARGET/skills/team-orchestrator"
  run cp -R "$HERE/skills/orchestrator" "$SKILL_DST"
  for f in "$HERE"/agents/orch-*.md; do run cp "$f" "$TARGET/agents/"; done
  echo "installed skill -> $SKILL_DST, $(ls "$HERE"/agents/orch-*.md | wc -l | tr -d ' ') agents -> $TARGET/agents ($SCOPE scope)"
fi
run mkdir -p "$STABLE"
for f in limits.py statusline.py checkpoint.py costs.py; do run cp "$HERE/skills/orchestrator/scripts/$f" "$STABLE/$f"; done

SETTINGS="$CONFIG/settings.json"; [ "$SCOPE" = project ] && SETTINGS="$TARGET/settings.json"
LEGACY=0; [ -f "$SETTINGS" ] && grep -q "team-orchestrator" "$SETTINGS" && LEGACY=1   # v1 entries are migrated
if [ $STATUSLINE -eq 1 ] || [ $HOOKS -eq 1 ] || [ $LEGACY -eq 1 ]; then
  [ $DRY -eq 1 ] && { echo "[dry-run] would patch $SETTINGS (statusline=$STATUSLINE hooks=$HOOKS v1-migration=$LEGACY)"; exit 0; }
  python3 "$HERE/scripts/patch_settings.py" install "$SETTINGS" "$STABLE" "$STATUSLINE" "$HOOKS"
fi
echo "done. Check: python3 \"$STABLE/limits.py\"   •   in Claude Code: /orchestrator <task>   (or: /orchestrator status)"
