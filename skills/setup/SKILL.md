---
name: setup
description: One-time setup for Claude Orchestrator plugin users — turns on the limits-aware status line (exact 5-hour and weekly usage on Pro/Max plans) by copying the scripts to ~/.claude/claude-orchestrator and adding a statusLine entry to ~/.claude/settings.json (backed up first; an existing status line is kept).
disable-model-invocation: true
argument-hint: "[remove]"
allowed-tools: Bash(bash:*), Bash(python3:*)
---
If `$ARGUMENTS` is `remove`: run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/patch_settings.py" uninstall "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"`
(removes only Orchestrator's status line and hooks entries, restores the previous status line, keeps a backup;
the data folder `~/.claude/claude-orchestrator/` with calibration and an optional `limits.json` stays), confirm in
one line and stop.

Otherwise the user wants to turn on Claude Orchestrator's status line. In one line, tell them what changes: the scripts are
copied to `~/.claude/claude-orchestrator/`, `~/.claude/settings.json` gets a `statusLine` entry, a backup
`settings.json.bak-<time>` is made, and an existing status line is kept (shown after ours). Then run:

    bash "${CLAUDE_PLUGIN_ROOT}/install.sh" --statusline-only

Check with `python3 ~/.claude/claude-orchestrator/limits.py` (use `$CLAUDE_CONFIG_DIR` instead of `~/.claude`
if it is set) and tell the user, in their language:
- the line appears at the bottom of Claude Code after the next message (restart Claude Code if it does not),
  e.g. `Opus 5.5 · ctx 41% · 5h 63% ↻14:50 · 7d 22%`; 5h/7d appear on Pro/Max plans after the first reply;
- it also feeds exact numbers to the orchestrator's limit checks and calibration;
- to undo: `/orchestrator:setup remove` (do it before uninstalling the plugin).
