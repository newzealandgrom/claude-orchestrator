#!/usr/bin/env bash
# Remove a manual install of Claude Orchestrator (plugin installs: `claude plugin uninstall orchestrator`).
#   ./uninstall.sh [--project <dir>]
# Removes the skill, the orch-* agents, the stable scripts copy and data (~/.claude/claude-orchestrator),
# and the status line / hooks entries that point to them (settings.json is backed up first). Also cleans up
# a v1 "team-orchestrator" install. Your other settings are untouched.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; TARGET="$CONFIG"; SETTINGS="$CONFIG/settings.json"
if [ "${1:-}" = "--project" ]; then TARGET="$(cd "$2" && pwd)/.claude"; SETTINGS="$TARGET/settings.json"; fi
rm -rf "$TARGET/skills/orchestrator" "$TARGET/skills/team-orchestrator"
rm -f "$TARGET"/agents/orch-*.md
rm -rf "$CONFIG/claude-orchestrator" "$CONFIG/team-orchestrator"
[ -f "$SETTINGS" ] && python3 "$HERE/scripts/patch_settings.py" uninstall "$SETTINGS"
# the user-level status line may point to us even after a --project install
[ "$SETTINGS" != "$CONFIG/settings.json" ] && [ -f "$CONFIG/settings.json" ] && grep -q "claude-orchestrator\|team-orchestrator" "$CONFIG/settings.json" \
  && python3 "$HERE/scripts/patch_settings.py" uninstall "$CONFIG/settings.json"
echo "Claude Orchestrator removed from $TARGET"
