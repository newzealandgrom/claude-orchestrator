---
name: status
description: Claude Orchestrator dashboard — the active plan's progress and checkpoint, running agents, limits mode and token spend against the plan budget.
disable-model-invocation: true
allowed-tools: Bash(python3:*), ListAgents
---
Orchestrator status (`checkpoint.py --status`):

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/scripts/checkpoint.py" --status`

If the ListAgents tool is available, call it once to see which agents are still running. Then give the user a
dashboard in their language, at most 12 lines: plan name and progress (done / in progress / to do), what is in
flight (agent ids and tasks), the next step, open decisions waiting for the user, limits mode and reset time,
tokens spent and the budget level. If there is no in-progress plan, say so and show only limits and costs.
