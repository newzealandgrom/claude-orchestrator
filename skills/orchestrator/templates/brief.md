ROLE: orch-<role> · PLAN: .claude/plans/<file>.md, step <N>
GOAL: <one sentence — what must be true after your work>

CONTEXT (ready-made, do not search again):
- <file>:<A>-<B> — <what is there> → read with `sed -n A,Bp <file>`
- Spec / finding: <doc>:<A>-<B> — the "fix" section is mandatory to follow
- Already done by other steps: <short>

DO:
1. …
2. …

CONSTRAINTS:
- You may edit only: <files/dirs>. Everything else: report, do not touch.
- Do not change: <crypto, limits, configs, production, …>
- <monolith file> is edited only by you right now.

DONE WHEN:
- <verifiable statement>
- <negative scenario that must fail safely>

VERIFY (run yourself, attach output):
- `<command 1>`
- `<command 2>`

PRODUCTION: do not touch. | OWNER_APPROVED: yes — allowed exactly: <actions>; rollback: <command>.
REPORT FORMAT: data for the orchestrator — changes as `file:lines — what`, command outputs, deviations with reasons,
what is not done. No prose.
