# Examples

Примеры: готовые промпты на английском и русском, заполненные план и бриф, три разобранные сессии и образцы вывода скриптов.

Names, ids and numbers here are illustrative; the commands, file formats and report texts are real. [plan-feature.md](plan-feature.md), [sessions/02-feature.md](sessions/02-feature.md) and the three files in `outputs/` describe the same imaginary run, so their numbers agree.

| File | What it is |
|---|---|
| [prompts.md](prompts.md) | 46 copy-paste prompts (English and Russian) by task type, each with a note on what the orchestrator will do |
| [plan-feature.md](plan-feature.md) | a filled plan (password reset by e-mail) halfway through: steps with `[x]`/`[~]`/`[ ]`, roles, budget, production gate, checkpoint |
| [brief-bugfix.md](brief-bugfix.md) | a filled agent brief for a bugfix, with `file:line` ranges, acceptance criteria and commands |
| [sessions/01-bugfix.md](sessions/01-bugfix.md) | walkthrough: a bugfix with the test first, an adversarial review and a rework round |
| [sessions/02-feature.md](sessions/02-feature.md) | walkthrough: a feature with economy mode, a budget warning, a context checkpoint and `/compact` recovery |
| [sessions/03-security-audit.md](sessions/03-security-audit.md) | walkthrough: a security audit with Fable off (Opus, effort max) and a refute panel for a critical finding |
| [outputs/limits.txt](outputs/limits.txt) | sample output of `python3 scripts/limits.py` (what `/orchestrator:limits` explains) |
| [outputs/costs.txt](outputs/costs.txt) | sample output of `python3 scripts/costs.py` with a plan budget line (`/orchestrator:costs`) |
| [outputs/status.txt](outputs/status.txt) | sample `/orchestrator:status` dashboard, shortened with `...` |
| [limits.example.json](limits.example.json) | optional config for `~/.claude/claude-orchestrator/limits.json` |

Start with [sessions/01-bugfix.md](sessions/01-bugfix.md) (the shortest), then pick a prompt from [prompts.md](prompts.md).

Related: the [playbooks](../skills/orchestrator/references/playbooks.md) behind the sessions, the [plan](../skills/orchestrator/templates/plan.md) and [brief](../skills/orchestrator/templates/brief.md) templates, and the [usage guide](../docs/en/usage-guide.md).
