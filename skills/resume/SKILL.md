---
name: resume
description: Resume Claude Orchestrator's in-progress plan after /compact, /clear, a restart or a limit reset — reload the checkpoint and continue.
disable-model-invocation: true
allowed-tools: Bash(python3:*), Skill
---
Checkpoint of the in-progress plan (`checkpoint.py`):

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/scripts/checkpoint.py"`

If nothing is printed above, tell the user there is no in-progress plan in `.claude/plans/` and stop.
Otherwise load the orchestrator skill with the Skill tool (`orchestrator:orchestrator`, args `resume`) and
continue from the Checkpoint: re-read the plan file, check limits first, and resume finished or failed
agents with SendMessage instead of re-briefing them.
