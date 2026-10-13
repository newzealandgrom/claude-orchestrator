# Roles (agents `orch-*`, plugin form `team-orchestrator:orch-*`)

| Role | Agent | Model / effort | Writes code | Production | When |
|---|---|---|---|---|---|
| Architect / tech lead | `orch-architect` | best / high | no | no | plan or spec review for L tasks; second opinion; judge |
| Analyst | `orch-analyst` | sonnet / high | no | no | vague request → requirements, acceptance criteria; docs vs code drift |
| Senior developer | `orch-dev-senior` | opus / high | yes | no | cross-cutting, protocol, concurrency, multi-module changes |
| Middle developer | `orch-dev-middle` | sonnet / medium | yes | no | well-specified change in one module |
| Junior developer | `orch-dev-junior` | haiku / medium | yes | no | exact diff, renames, mechanical edits |
| DevOps / SRE | `orch-devops` | opus / medium | infra files | read-only unless `OWNER_APPROVED: yes` | snapshots, deploy plans with rollback, deploys |
| Security / pentest | `orch-security` | best / high | no | non-destructive read-only | threat model, auth, perimeter, rate limits, confirming findings |
| Protocol / crypto reviewer | `orch-protocol-reviewer` | best / high | no | no | crypto, auth tokens, wire formats, cross-platform compatibility, test vectors |
| Adversarial reviewer | `orch-reviewer` | opus / high | no | no | every dev step; tries to refute "done", runs builds |
| QA / user voice | `orch-qa` | sonnet / medium | no | no | scenarios, smoke checklists, UX traps, false promises in UI |
| Build verifier | `orch-build-verifier` | haiku / low | no | no | run listed commands, PASS/FAIL + error lines |
| Scout | `orch-scout` | haiku / low | no | no | `file:line` maps; navigating huge documents |
| Designer / frontend | `orch-designer` | opus / medium | styles/components | no | screens, design tokens, accessibility, microcopy |
| Tech writer | `orch-tech-writer` | sonnet / medium | docs | no | README, changelogs, runbooks, public summaries — every claim checked against code |
| Toolsmith | `orch-toolsmith` | sonnet / medium | no | no | find and vet plugins/skills/MCP/LSP for a domain; never installs |

Fallbacks (from `limits.py`): Fable `off` → `best` roles run as `model: "opus", effort: "max"`; Opus `off` →
senior roles on Sonnet high.

## Typical teams

| Task | Order |
|---|---|
| One backend finding | scout → dev-middle/senior → build-verifier → reviewer (+ protocol-reviewer for auth/crypto) |
| Cross-platform change | scouts per platform ∥ → architect (spec) → devs per platform ∥ (worktrees if one build tree) → build-verifier → protocol-reviewer + reviewers ∥ → fix rounds |
| Production change | devops read-only snapshot → security (what it closes/breaks) → **user's yes** → devops with `OWNER_APPROVED: yes` → post-checks |
| Something broke | devops snapshot ∥ scout → dev-senior → build-verifier → reviewer → deploy after yes |
| Module review/audit | security ∥ protocol-reviewer ∥ reviewer (one brief, three lenses) → dedupe → refute panel for criticals |
| New UI feature | analyst → designer → devs → build-verifier → qa → reviewer |
| Docs after release | tech-writer (+ qa checklist) |
| New stack/domain | toolsmith → install per policy → domain agent with the tool named in its brief |
