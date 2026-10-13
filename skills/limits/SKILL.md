---
name: limits
description: Show Claude Orchestrator's limits report — 5-hour and weekly usage, per-model status (Fable/Opus/Sonnet/Haiku), context fill, calibration and the routing actions the orchestrator will follow.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---
Current limits report (Claude Orchestrator, `limits.py`):

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/scripts/limits.py"`

Explain this report to the user in their language in at most 8 lines: the mode and what it means for the work
(how many heavy agents, which models), each model's status, the context fill, when the 5-hour window resets
(convert UTC to the user's local time if known), and the listed actions. If the source is `transcripts` only,
add one line: enabling the status line (`install.sh --statusline-only`) gives exact official numbers.
