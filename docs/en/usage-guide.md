# Usage guide

[Русская версия](../ru/usage-guide.md) · [README](../../README.md) · [Limits and context](limits-and-context.md)

This guide walks through one orchestrated task from request to report, then covers resuming, writing briefs,
parallel work and keeping costs down. Everything described here comes from the skill itself
(`skills/team-orchestrator/SKILL.md` and `references/`).

## Starting

```
/team-orchestrator <task>            # a new task
/team-orchestrator resume            # continue the plan in .claude/plans/ with status in-progress
/team-orchestrator .claude/plans/2026-10-13-api-tests.md   # continue a specific plan
```

The skill is also selected automatically when your request matches its description (multi-file or multi-platform
changes, audits and their fixes, releases, deployments, reviews). In a plugin install the long form is
`/team-orchestrator:team-orchestrator`. The orchestrator answers in your language.

## Lifecycle

### 0. Limits gate

First step, and again before every wave of agents: `python3 scripts/limits.py`. It prints `mode`, per-model status,
context fill and a list of actions the orchestrator then follows. See [limits-and-context.md](limits-and-context.md).

### 1. Size

| Size | Signs | What happens |
|---|---|---|
| S | at most 2 files, obvious fix, no security/production/protocol | The orchestrator does it itself; no agents. |
| M | 2–6 steps, 1–2 areas | Short plan, 2–5 agents, verification. |
| L | several platforms/services, protocol/crypto/security, production, a batch of audit findings, a new feature | Full cycle; an architect reviews the plan first. |

### 2. Recon (cheap)

- The project map `.claude/orchestrator/project-map.md` is read; if it is missing, `orch-scout` (Haiku) builds it
  from `references/project-map-template.md` (structure, build/test commands, production facts, traps).
- Existing memory and `.claude/plans/` are checked.
- Scouts return `file:line — what` maps, one per area, in parallel. `orch-devops` can take a read-only production
  snapshot. The orchestrator opens code itself only to accept results.

### 3. Plan

A file `.claude/plans/YYYY-MM-DD-<slug>.md` from `templates/plan.md`: steps with `file:lines`, role and model/effort,
dependencies, what runs in parallel, "done when" and a verification command per step, a production gate, a token
estimate and a `## Checkpoint` section. For L tasks `orch-architect` reviews it and every disagreement is resolved
explicitly. You get a 5–12 line summary; the orchestrator continues unless the next step is irreversible or touches
production.

### 4. Execute

- Each agent gets a brief from `templates/brief.md` — it is the agent's only context.
- One writer per file; parallel writers on one build tree go into separate git worktrees.
- Background agents notify on completion; the orchestrator does not predict their results.
- Escalation: cheapest adequate model first; on failure the next tier with the same brief plus the failure reason.

### 5. Verify

Proportional to risk, never on the developer's word: `orch-build-verifier` always; `orch-reviewer` for every dev step;
`orch-protocol-reviewer` for crypto, auth, wire formats; `orch-security` for auth, perimeter, rate limits and
production config; `orch-qa` for user flows. A "rework" verdict goes back to the same developer via `SendMessage`
(context kept), then only the fixes are re-reviewed. Critical findings get a refute panel of three independent
reviewers (accepted at two or more). See `references/verification.md`.

### 6. Production gate

Deploy, restart, config or firewall changes, `git push`, publishing, deletion, secret rotation — nothing happens
without your explicit "yes" for that step in the current conversation, unless your request explicitly orders exactly
that action. Order: read-only snapshot -> plan with backup and rollback -> your "yes" -> `orch-devops` brief with
`OWNER_APPROVED: yes` and the exact action list -> post-change checks. See `references/production-gate.md`.

### 7. Finish

The plan gets status `done` and a "Result" section (done / not done and why / verified how / owner actions /
tokens). Durable facts go to the project map. The final report says what changed, how it was verified (commands ->
results), what is left and what needs your decision.

## Example session (abridged, illustrative)

```
you      > /team-orchestrator fix the failing tests in api/ and add coverage

orch     > [limits] mode normal, fable ok, context 6%.
           Size: M (api/ only, 2 areas: handlers + tests). Recon first.
orch     > scout (haiku): api/ map, test commands -> .claude/orchestrator/project-map.md updated
orch     > Plan .claude/plans/2026-10-13-api-tests.md
           1. orch-build-verifier: run `pytest api/ -x -q`, list failures        (haiku/low)
           2. orch-dev-middle: fix handlers failing in api/orders.py:40-120       (sonnet/medium)
           3. orch-dev-middle: add coverage for api/orders.py (separate file)     (sonnet/medium)   parallel with 2
           4. orch-build-verifier + orch-reviewer on both diffs                   (haiku/low, opus/high)
           Production: not touched. Estimate ~0.4M tokens. Continuing.
orch     > step 1: 3 failures, all in api/orders.py (lines 58, 77, 112)
orch     > steps 2 and 3 running in parallel (different files, same build tree -> sequential pytest runs only)
orch     > step 2 done; step 3 done
orch     > build-verifier: PASS (41 passed). reviewer: rework — missing negative case for empty cart
orch     > SendMessage to the step-3 developer: add the case; reviewer re-checks only the fix
orch     > accepted.

Report
  Changed: api/orders.py:58-64,77-81,112-118 (fixes); tests/test_orders.py (+9 tests)
  Verified: pytest api/ -q -> 50 passed; reviewer round 2: accepted
  Not verified: behaviour under load
  Left / decisions: none
```

The numbers and file names above are made up to show the shape of a session, not real output.

## Resuming

**After `/compact`, `/clear` or `--resume`.** The plugin's `SessionStart` hook (matcher `compact|resume|clear`)
finds the newest plan in `.claude/plans/*.md` whose header says `in-progress`, and injects its header, the
`## Checkpoint` section and a one-line limits summary into the fresh context. Then run
`/team-orchestrator resume` if the orchestrator does not continue by itself.

**After a limit.** In `exhausted` mode the orchestrator launches nothing, writes the checkpoint and tells you the
reset time. After the reset, say `resume`: failed or finished agents are continued with `SendMessage`
("Limit reset — continue from where you stopped and return the result in the agreed format."), not re-briefed.

**Asking for `/compact`.** The model cannot run `/compact`. At 75 % context it writes the checkpoint and asks you to
run it, with a keep-string such as `/compact keep: plan <path>, running agents, next step`.

A good checkpoint (template section) lists: done, in flight (agent id and what it does), next step, open
decisions or questions waiting for you, key paths. If you edit the plan by hand, keep the line
`**Status:** in-progress` in the first 4000 characters — the hook looks for it there (`checkpoint.py` accepts also
the Russian words «статус» and «чекпоинт»).

## Writing good briefs

If you brief agents yourself (or review what the orchestrator wrote), use `templates/brief.md`:

```
ROLE: orch-<role> · PLAN: .claude/plans/<file>.md, step <N>
GOAL: <one sentence — what must be true after your work>

CONTEXT (ready-made, do not search again):
- <file>:<A>-<B> — <what is there> → read with `sed -n A,Bp <file>`

DO:
1. …

CONSTRAINTS:
- You may edit only: <files/dirs>. Everything else: report, do not touch.

DONE WHEN:
- <verifiable statement>
- <negative scenario that must fail safely>

VERIFY (run yourself, attach output):
- `<command>`

PRODUCTION: do not touch.
REPORT FORMAT: changes as `file:lines — what`, command outputs, deviations with reasons, what is not done.
```

Rules of thumb: give ranges (`file:A-B`), not whole files; list the files the agent may edit; state a negative
scenario; ask for a structured report instead of prose; put production permission explicitly
(`PRODUCTION: do not touch` or `OWNER_APPROVED: yes — allowed exactly: …; rollback: …`).

## Parallel work

- One writer per file. A large controller or server file is edited by one agent at a time.
- Different files in one compiled tree (one gradle/xcode/npm project) can still break each other's builds. Run the
  second writer with `isolation: "worktree"`; it commits on its own branch and reports the hash. The orchestrator
  merges without committing:

```bash
git cherry-pick -n <sha>
```

  This works on a dirty tree as long as the touched files are not modified there. Follow-up fixes become new commits
  and are cherry-picked the same way. Add `.claude/worktrees/` to the repository's `.gitignore`.
- At most one heavy build per tool at a time per tree; use separate derived-data directories for parallel Xcode
  builds.
- Fan-out limits: `normal` up to 4 heavy agents, `economy` up to 2, `critical` none new.
- Check that new source files are not silently ignored (`git status --short --ignored <dir>`).

## Project map

`.claude/orchestrator/project-map.md` (at most about 150 lines) is read often, so it stays short: what the project is,
components and sizes, build/test/lint commands, specs worth knowing, production facts (read-only), traps. The scout
builds it on first use; the orchestrator updates it when it goes stale. The template is
`references/project-map-template.md`. Commit it or ignore it as you prefer. Do not put secrets in it: it is read often and may be committed.

## Keeping costs low

- Let small tasks stay small: S tasks are done directly.
- Pass maps and ranges in briefs so expensive agents do not search.
- Prefer resuming an agent (`SendMessage`) over re-briefing a new one.
- Cheapest adequate model first; Fable/`best` only for architecture, security, protocol and critical judgement.
- Ask for compact reports; do not paste big files or full diffs into the orchestrator's chat.
- Install the status line and watch `ctx` — checkpoint early rather than compacting in a hurry.
- Use `economy` mode as a signal, not an obstacle: it exists to keep a task finishable before the window resets.
- Rough per-agent cost guide (from `references/model-routing.md`): scout 5–50k tokens, build-verifier 5–30k,
  junior 10–30k, middle 30–100k, senior 60–500k, reviewer 40–300k, architect/protocol/security 60–300k. A plan with
  five dev steps and full verification: 0.5–1.5M; a cross-platform protocol change with review rounds: 3–7M.
