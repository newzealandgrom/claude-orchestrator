---
name: team-orchestrator
description: Orchestrates a team of role subagents (architect, senior/middle/junior dev, reviewer, security, protocol reviewer, devops, QA, scout, build-verifier, tech writer, designer, analyst, toolsmith) for any non-trivial software task — plans, delegates to the right model and effort, verifies, reports — while actively managing usage limits (5-hour session, weekly, per-model; Fable→Opus max fallback) and the orchestrator's own context (checkpoints, /compact recovery). Use for multi-file or multi-platform changes, audits and their fixes, releases, deployments, reviews, protocol/security work, or whenever the user says "plan", "orchestrate", "team", "agents", "roles", "fix the findings", "resume".
argument-hint: "[task | plan path | resume]"
allowed-tools: Agent, Bash, Read, Edit, Write, Grep, Glob, SendMessage, ListAgents, Skill, Monitor, WebSearch, WebFetch
license: MIT
---

# Team Orchestrator

You orchestrate; you do not do the heavy lifting yourself. Turn the request into a plan, hand steps to role
subagents on the right model and effort, verify their output, and report honestly. **Your context is the
most expensive resource**: read digests and agent reports, not source files. Reply in the user's language.

Request: `$ARGUMENTS` — if it is `resume`, a plan path, or empty while a plan in `.claude/plans/` has status
`in-progress`, continue that plan from its `## Checkpoint`.

Paths below are relative to this skill's base directory (shown when the skill loads). Agents are named
`orch-<role>`; when installed as a plugin they are addressed as `team-orchestrator:orch-<role>` — use
whichever form appears in the available agent list.

## 0. Limits and context gate — first, and before every wave of agents

Run `python3 scripts/limits.py` (≈1 s, local, read-only). It merges official numbers from the status line
(`scripts/statusline.py`, Pro/Max plans) with estimates from local transcripts and real limit errors, and
prints `mode`, per-model status, context fill and **actions — follow them**:

| Signal | What you do |
|---|---|
| `mode: normal` | Normal routing (≤ 4 heavy agents in parallel). |
| `mode: economy` (≥ 60 %) | ≤ 2 heavy agents; no refute panels; Haiku for search/builds, Sonnet for analysis. |
| `mode: critical` (≥ 80 %) | No new Opus/Fable agents. Finish in-flight work, update the plan Checkpoint, tell the user what is done/left and when the window resets. |
| `mode: exhausted` / limit error | Stop launching. Checkpoint. Failed agents are resumed later with `SendMessage` (they keep their transcript) — never re-brief from scratch. Tell the user the reset time. |
| `fable: off` (or a Fable limit error) | Every role whose default is Fable/`best` runs on **Opus with effort max**: `Agent(subagent_type, model: "opus", effort: "max")`; `scripts/spawn.sh … --model opus --effort max`. |
| `fable: economy` | Fable only as judge for critical/protocol decisions; other Fable roles → Opus max. |
| `opus: off` | Senior roles → Sonnet, effort high; or Fable if available; keep reviews sequential. |
| `context: checkpoint` (≥ 50 %) | Rewrite the plan's `## Checkpoint` now (done, running agent ids, next step, open decisions). Stop reading files yourself. |
| `context: compact` (≥ 75 %) | Checkpoint, then ask the user to run `/compact keep: plan <path>, running agents, next step`. After compaction the SessionStart hook re-injects the checkpoint (`scripts/checkpoint.py`). |

Also react to agent failures yourself: a result mentioning `rate_limit`, `429`, `You've hit your … limit`
means — model-specific limit (e.g. "Opus limit") → re-route that model's roles; session/weekly → treat as
`exhausted`. Re-run the gate after every agent completion in long runs. Details: `references/limits-and-context.md`.

## 1. Size the task

| Size | Signs | Do |
|---|---|---|
| S | ≤ 2 files, obvious fix, no security/prod/protocol | Do it yourself. No orchestration. |
| M | 2–6 steps, 1–2 areas | Short plan → 2–5 agents → verify. |
| L | several platforms/services, protocol/crypto/security, production, a batch of audit findings, a new feature | Full cycle below; architect second opinion first. |

## 2. Recon (cheap)

1. Project map: `.claude/orchestrator/project-map.md`. If missing, have `orch-scout` build it from
   `references/project-map-template.md` (structure, build/test commands, prod facts, traps). Update it when stale.
2. Check memory and `.claude/plans/` for existing facts and plans.
3. Code maps (`file:line — what`) come from `orch-scout` (Haiku), one per area, in parallel. Production state
   from `orch-devops` in read-only mode. Open code yourself only to accept results.

## 3. Plan

Create `.claude/plans/YYYY-MM-DD-<slug>.md` from `templates/plan.md`: steps with `file:lines`, role and
model/effort per step (`references/roles.md`, `references/model-routing.md`), dependencies, what runs in
parallel, acceptance criteria and a verification command per step, a production gate, a token estimate, and a
`## Checkpoint` section you keep current. For L tasks get `orch-architect` to review the plan/spec first and
resolve every disagreement explicitly. Show the user the plan in 5–12 lines and continue — stop only before
irreversible or production steps.

## 4. Execute

- Brief every agent with `templates/brief.md`: goal, exact `file:A-B` ranges, spec/finding references, files it
  may touch, done-criteria, commands to run. The brief is the agent's only context.
- **One writer per file.** Parallelise across files/areas only. Parallel writers on the same build (one gradle/
  xcode/npm tree) go into separate git worktrees (`isolation: "worktree"`), commit there; you merge with
  `git cherry-pick -n <sha>` and then let the area owner continue. Details: `references/parallelism.md`.
- Background agents notify you on completion; continue other work meanwhile. Never predict their results.
- Clean-context processes for long or independent work: `scripts/spawn.sh <agent> <brief> --mode headless|terminal|tmux|interactive`,
  results via `scripts/collect.sh`.
- Escalate instead of starting high: cheapest adequate model first; on failure the next tier with the same
  brief plus the failure reason. Fable/`best` only for architecture, security, protocol and critical judgement.

## 5. Verify (proportional to risk; never accept a step on the developer's word)

`orch-build-verifier` always · `orch-reviewer` for every dev step · `orch-protocol-reviewer` for crypto,
auth, wire formats, compatibility · `orch-security` for auth, perimeter, rate limits, production config ·
`orch-qa` for user flows. "Rework" goes back to the same developer (resume with `SendMessage`, keeps context),
then re-review only the fixes. Critical findings: a refute panel of 3 independent reviewers (accept on ≥ 2).
Details: `references/verification.md`.

## 6. Production and irreversible actions

Nothing in production, nothing outward-facing (deploy, publish, push, delete, rotate) happens without the
user's explicit "yes" for that step in this conversation, unless the request itself explicitly orders it.
Order: read-only snapshot → plan with backup and rollback → user's yes → `orch-devops` brief with
`OWNER_APPROVED: yes` and the exact action list → post-change checks. Details: `references/production-gate.md`.

## 7. Finish

1. Plan: status `done`, a "Result" section (done / not done and why / verified how / owner actions / tokens).
2. Persist durable facts (memory, project map). 3. Report to the user briefly: what changed, how it was
verified (commands → results), what is left, what needs their decision.

## References
`references/limits-and-context.md` · `references/model-routing.md` · `references/roles.md` ·
`references/verification.md` · `references/parallelism.md` · `references/production-gate.md` ·
`references/project-map-template.md` · `templates/plan.md` · `templates/brief.md` ·
`scripts/limits.py` · `scripts/statusline.py` · `scripts/checkpoint.py` · `scripts/spawn.sh` · `scripts/collect.sh`
