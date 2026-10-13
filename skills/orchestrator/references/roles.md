# Roles (agents `orch-*`, plugin form `orchestrator:orch-*`)

27 roles in 6 groups. `best` = Fable if the account has it, otherwise Opus. "Writes" = may edit files.

| Group | Role | Agent | Model / effort | Writes | When |
|---|---|---|---|---|---|
| Lead | Architect / tech lead | `orch-architect` | best / high | no | plan or spec review for L tasks; second opinion; judge |
| Lead | Analyst | `orch-analyst` | sonnet / high | no | vague request → requirements, acceptance criteria; docs vs code drift |
| Lead | Researcher | `orch-researcher` | sonnet / medium | no | questions that need the web: libraries, standards, prior art — with sources |
| Build | Senior developer | `orch-dev-senior` | opus / high | code | cross-cutting, protocol, concurrency, multi-module changes |
| Build | Middle developer | `orch-dev-middle` | sonnet / medium | code | well-specified change in one module |
| Build | Junior developer | `orch-dev-junior` | haiku / medium | code | exact diff, renames, mechanical edits |
| Build | Frontend developer | `orch-frontend` | sonnet / medium | code | web UI: components, state, forms, states, responsive |
| Build | Mobile developer | `orch-mobile` | opus / medium | code | iOS/Android: lifecycle, permissions, secure storage, parity |
| Build | Database engineer | `orch-db-engineer` | opus / medium | migrations, queries | schemas, safe migrations with rollback, indexes, query plans |
| Build | API designer | `orch-api-designer` | sonnet / high | specs | contracts, error model, versioning, compatibility — before code |
| Build | Designer | `orch-designer` | opus / medium | styles, components | screens, design tokens, microcopy |
| Quality | Adversarial reviewer | `orch-reviewer` | opus / high | no | every dev step; tries to refute "done", runs builds |
| Quality | Test engineer | `orch-test-engineer` | sonnet / medium | tests | missing tests, coverage gaps, flaky tests, test vectors |
| Quality | QA / user voice | `orch-qa` | sonnet / medium | no | scenarios, smoke checklists, UX traps, false promises in UI |
| Quality | Performance engineer | `orch-performance` | opus / high | code | measured optimisation: profiles, benchmarks, N+1, leaks |
| Quality | Accessibility reviewer | `orch-accessibility` | sonnet / medium | no | WCAG 2.2 AA, screen readers, contrast, keyboard, text scaling |
| Quality | Build verifier | `orch-build-verifier` | haiku / low | no | run listed commands, PASS/FAIL + error lines |
| Security | Security / pentest | `orch-security` | best / high | no | threat model, auth, perimeter, rate limits, confirming findings |
| Security | Protocol / crypto reviewer | `orch-protocol-reviewer` | best / high | no | crypto, auth tokens, wire formats, cross-platform compatibility |
| Security | Privacy engineer | `orch-privacy-compliance` | sonnet / high | no | personal-data map, PII in logs, policy vs behaviour |
| Security | Dependency auditor | `orch-dependency-auditor` | sonnet / medium | no | CVEs with reachability, outdated/abandoned packages, licences |
| Ops | DevOps / SRE | `orch-devops` | opus / medium | infra files | snapshots, deploy plans with rollback; prod only with `OWNER_APPROVED: yes` |
| Ops | Incident responder | `orch-incident-responder` | opus / high | no | production is broken: triage, hypotheses, safe mitigation |
| Ops | Release manager | `orch-release-manager` | sonnet / medium | version, changelog | semver bump, release notes, checklist; publishes only with approval |
| Support | Scout | `orch-scout` | haiku / low | no | `file:line` maps; navigating huge documents |
| Support | Tech writer | `orch-tech-writer` | sonnet / medium | docs | README, changelogs, runbooks — every claim checked against code |
| Support | Toolsmith | `orch-toolsmith` | sonnet / medium | no | find and vet plugins/skills/MCP/LSP for a domain; never installs |

Fallbacks (from `limits.py`): Fable `off` → `best` roles run as `model: "opus", effort: "max"`; Opus `off` →
senior roles on Sonnet high. Read-only roles have `disallowedTools: Edit, Write, NotebookEdit`.

## Typical teams (full recipes: `playbooks.md`)

| Task | Order |
|---|---|
| One bug | scout → dev-middle/senior → test-engineer (regression test) → build-verifier → reviewer |
| New feature | analyst → architect (L) ∥ api-designer → devs per area ∥ (frontend / mobile / db) → test-engineer → build-verifier → reviewer → qa (+ accessibility for UI) → tech-writer |
| Cross-platform change | scouts per platform ∥ → architect (spec) → devs per platform ∥ (worktrees if one build tree) → build-verifier → protocol-reviewer + reviewers ∥ → fix rounds |
| Refactor | scout → architect → dev-senior (small steps) → test-engineer (safety net first) → build-verifier → reviewer |
| DB migration | db-engineer (migration + rollback) → reviewer → test on a copy → devops plan → **user's yes** → devops |
| Dependency upgrade | dependency-auditor → dev-middle per package group → build-verifier → test-engineer → reviewer |
| Security audit | security ∥ protocol-reviewer ∥ privacy-compliance ∥ dependency-auditor → dedupe → refute panel for criticals → fixes as bugs |
| Performance | performance (baseline) → dev-senior/performance (fix) → build-verifier → performance (after) → reviewer |
| Incident | incident-responder ∥ devops snapshot → mitigation plan → **user's yes** → devops → incident-responder (verify) → tech-writer (postmortem) |
| Release | release-manager → build-verifier (full matrix) → qa smoke → **user's yes** → release-manager/devops publish |
| Docs | scout → tech-writer → reviewer (claims vs code) |
| Unknown codebase | scouts per area ∥ → analyst → tech-writer (project map) |
| New stack/domain | toolsmith ∥ researcher → install per policy → domain agent with the tool named in its brief |
| Production change | devops read-only snapshot → security (what it closes/breaks) → **user's yes** → devops with `OWNER_APPROVED: yes` → post-checks |
