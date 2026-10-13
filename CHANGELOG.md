# Changelog

## 1.0.0 — 2026-10-13
- First public release: `team-orchestrator` skill + 15 role subagents (`orch-*`), plugin + marketplace in one repo.
- Limits gate: `scripts/limits.py` (5-hour session, weekly, per-model; calibration from real limit errors and
  "used N%" warnings; official status-line numbers on Pro/Max), automatic Fable → Opus (effort max) re-routing.
- Context management: plan checkpoints, `/compact` guidance, `SessionStart` hook re-injects the active plan checkpoint.
- Hooks: `SessionStart` (compact|resume|clear), `PostToolUse` (Agent), `UserPromptSubmit`.
- `statusline.py` (model · context · 5h · 7d, chains an existing status line), `spawn.sh`/`collect.sh` for clean-context
  agent processes, `install.sh`/`uninstall.sh` for manual installs.
