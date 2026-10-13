---
name: costs
description: Claude Orchestrator cost report — tokens and limit share per role and per agent in this session, top consumers, and the active plan's budget.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---
Session costs (`costs.py`):

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/scripts/costs.py" --top 8`

Active plan budget (empty when no in-progress plan has a `Budget:` line):

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/scripts/costs.py" --active-plan --budget-only`

Summarise for the user in their language, at most 10 lines: total spend (tokens and ≈ % of the 5-hour limit),
the three most expensive roles and agents with one-line reasons, the budget level if any, and one concrete
saving tip that fits the numbers (e.g. a role running on a more expensive model than its work needs).
