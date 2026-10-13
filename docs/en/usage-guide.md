# Usage guide

[Русская версия](../ru/usage-guide.md) · [README](../../README.md) · [Limits and context](limits-and-context.md)

Claude Orchestrator turns a non-trivial request into a plan, hands the steps to role subagents on the right model and
effort, verifies what comes back and reports — while watching your usage limits, your token spend and its own context
window. This guide covers installing it, the commands, one orchestrated task from request to report, the team of 27
roles and the playbooks, resuming, writing briefs, parallel work, and a set of ready-made recipes. Everything
described here comes from the skill itself ([`skills/orchestrator/SKILL.md`](../../skills/orchestrator/SKILL.md) and
[`references/`](../../skills/orchestrator/references/)). How limits, costs and context are handled is in
[Limits and context](limits-and-context.md).

## Install

Requirements: Claude Code (2.1.292 or newer is recommended because per-agent `effort` is used for model fallbacks; the
one-line install below needs 2.1.275 or newer), Python 3.9+ with the standard library only (nothing to `pip install`),
and macOS or Linux (on Windows use WSL — the scripts are bash and Python). With a Claude Pro/Max subscription the
status line shows exact official limit numbers; with an API key you get estimates.

### Inside Claude Code (recommended)

1. Open a terminal (macOS: Terminal or iTerm; Linux: any; Windows: WSL Ubuntu), go to a project folder and start
   Claude Code:

   ```bash
   cd ~/my-project
   claude
   ```

2. In Claude Code's input box (the prompt with `>`) type one line:

   ```
   /plugin install orchestrator --marketplace newzealandgrom/claude-orchestrator
   ```

   Claude Code older than 2.1.275 does not know the one-line form. Use two commands instead:

   ```
   /plugin marketplace add newzealandgrom/claude-orchestrator
   /plugin install orchestrator@claude-orchestrator
   ```

3. If the new commands do not appear right away, type `/reload-plugins` or restart Claude Code.

### From the terminal

Without opening Claude Code:

```bash
claude plugin install orchestrator --marketplace newzealandgrom/claude-orchestrator
```

Add `--scope project` to enable the plugin only for the current project (the default scope is user). On an older
Claude Code use the two-step form: `claude plugin marketplace add newzealandgrom/claude-orchestrator`, then
`claude plugin install orchestrator@claude-orchestrator`.

### Manual install (copy files, no plugin system)

```bash
git clone https://github.com/newzealandgrom/claude-orchestrator.git
cd claude-orchestrator
./install.sh
```

| Option | Effect |
|---|---|
| *(none)* | Skill and the 27 `orch-*` agents for your user (`~/.claude`). The scripts are also copied to `~/.claude/claude-orchestrator/`. |
| `--project <dir>` | Skill and agents for one project only (`<dir>/.claude`). |
| `--statusline` | Also enable the status line (patches `settings.json`). |
| `--hooks` | Also register the limits, budget and checkpoint hooks in `settings.json`. Plugin installs have them built in — do not use both. |
| `--statusline-only` | Only the status line, no skill or agents. This is what `/orchestrator:setup` runs for plugin users. |
| `--dry-run` | Show what would change; change nothing. |

`settings.json` is backed up to `settings.json.bak-<timestamp>` before any change, and `CLAUDE_CONFIG_DIR` is honoured.
A manual install gives the command `/orchestrator` (no prefix) and agents named `orch-<role>`.

### Check that it worked

- `/plugin` → the "Installed" tab shows `orchestrator`.
- `/agents` lists 27 agents named `orchestrator:orch-…`.
- Type `/orchestrator:` — the menu shows the commands.
- `/orchestrator:limits` prints the limits report.

### Status line (optional, recommended, one time)

A plugin cannot switch on a status line by itself, so this is a separate step. Plugin users type:

```
/orchestrator:setup
```

It runs `install.sh --statusline-only`: it copies the scripts to `~/.claude/claude-orchestrator/`, adds a `statusLine`
entry to `~/.claude/settings.json`, makes a backup `settings.json.bak-<time>` and keeps a status line you already
have (its output is shown after ours). Manual installs use `./install.sh --statusline`. The line appears after your
next message:

```
Opus 5.5 · ctx 41% · 5h 63% ↻14:50 · 7d 22%
```

On Pro/Max it also feeds exact numbers to the orchestrator's limit checks. After a plugin update the copy of the
scripts refreshes itself at the next session start. Details and undo: [Status line](limits-and-context.md#status-line).

## Starting

```
/orchestrator:orchestrator <task>            # a new task (plugin install)
/orchestrator <task>                         # the same, manual install
/orchestrator:orchestrator resume            # continue the plan in .claude/plans/ with status in-progress
/orchestrator:orchestrator .claude/plans/2026-05-04-password-reset.md   # continue a specific plan
```

You can also just say it in plain words — "Use the orchestrator to …". Claude loads the skill itself when your
request matches its description (multi-file or multi-platform changes, audits and their fixes, releases, deployments,
reviews). With an empty argument and a plan in progress, the orchestrator resumes that plan. It answers in your
language.

### Short commands

| Plugin install | Manual install | What you get |
|---|---|---|
| `/orchestrator:status` | `/orchestrator status` | A dashboard of at most 12 lines: plan progress (done / in progress / to do), what is running, the next step, decisions waiting for you, limits mode and reset time, spend against the budget. |
| `/orchestrator:limits` | `/orchestrator limits` | The limits report explained in a few lines: mode, per-model status, context fill, reset time, the actions the orchestrator will follow. |
| `/orchestrator:costs` | `/orchestrator costs` | Tokens and share of the limit per role and per agent, the top consumers, the plan's budget level and one saving tip. |
| `/orchestrator:resume` | `/orchestrator resume` | Reloads the checkpoint of the in-progress plan and continues; says so if there is no such plan. |
| `/orchestrator:setup` | `./install.sh --statusline` | One-time status line setup. `/orchestrator:setup remove` undoes it. |

The short commands are started by you; Claude does not run them on its own.

## Lifecycle

### 0. Limits gate

First step, and again before every wave of agents: `python3 scripts/limits.py` (about a second, local, read-only). It
prints `mode`, per-model status, context fill and a list of actions the orchestrator then follows. Hooks repeat the
check on their own, and `/orchestrator:limits` shows the same report any time. See
[limits-and-context.md](limits-and-context.md).

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

The closest [playbook](#playbooks) gives the team, the order, the checks and a rough budget hint. The plan is a file
`.claude/plans/YYYY-MM-DD-<slug>.md` from `templates/plan.md`. Its header holds the status (`in-progress`), the
`Started:` time, the `Budget:`, the playbook, the size and a token estimate. Each step has `file:lines`, a status
marker (`[ ]` to do, `[~]` in progress, `[x]` done — `/orchestrator:status` counts them), the role with model/effort,
dependencies, what runs in parallel, "done when" and a verification command. Below come a production gate, risks, a
`## Checkpoint` section that is kept current and a `## Result` section. For L tasks `orch-architect` reviews the plan
and every disagreement is resolved explicitly. You get a 5–12 line summary; the orchestrator continues unless the next
step is irreversible or touches production.

### 4. Execute

- Each agent gets a brief from `templates/brief.md` — it is the agent's only context.
- One writer per file; parallel writers on one build tree go into separate git worktrees.
- Background agents notify on completion; the orchestrator does not predict their results.
- Escalation: cheapest adequate model first; on failure the next tier with the same brief plus the failure reason.
- Long or independent work can run in a separate process with a clean context (see
  [Clean-context agents](#clean-context-agents)).

### 5. Verify

Proportional to risk, never on the developer's word:

- `orch-build-verifier` always; `orch-reviewer` for every dev step.
- `orch-protocol-reviewer` for crypto, auth, wire formats and compatibility; `orch-security` for auth, perimeter, rate
  limits and production config; `orch-privacy-compliance` when personal data is collected, logged or shared.
- `orch-qa` for user flows; `orch-accessibility` for UI; `orch-test-engineer` when behaviour changed without tests;
  `orch-performance` for hot paths; `orch-dependency-auditor` when dependencies change.

A "rework" verdict goes back to the same developer via `SendMessage` (context kept), then only the fixes are
re-reviewed. Critical findings get a refute panel of three independent reviewers (accepted at two or more). See
[`references/verification.md`](../../skills/orchestrator/references/verification.md).

### 6. Production gate

Deploy, restart, config or firewall changes, `git push`, publishing, deletion, secret rotation — nothing happens
without your explicit "yes" for that step in the current conversation, unless your request explicitly orders exactly
that action. Order: read-only snapshot → plan with backup and rollback → your "yes" → `orch-devops` brief with
`OWNER_APPROVED: yes` and the exact action list → post-change checks. See
[`references/production-gate.md`](../../skills/orchestrator/references/production-gate.md).

### 7. Finish

The plan gets status `done` and a "Result" section (done / not done and why / verified how / owner actions / tokens —
the actual spend comes from `costs.py --plan`). Durable facts go to the project map and memory. The final report says
what changed, how it was verified (commands → results), what is left and what needs your decision.

## The team: 27 roles

Agents are named `orch-<role>`; in a plugin install they are addressed as `orchestrator:orch-<role>`, and `/agents`
lists them. `best` means Fable if your account has it, otherwise Opus. **new** marks the 12 roles added in 2.0 (the
15 roles of 1.0 keep their names and defaults). Read-only roles have the `Edit`, `Write` and `NotebookEdit` tools
switched off in their agent files. The defaults live in `agents/orch-*.md`; the full table with typical teams is
[`references/roles.md`](../../skills/orchestrator/references/roles.md).

### Lead — plan and decide

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-architect` | best / high | read-only | Plan or spec review for L tasks, second opinion, judge of critical disputes. |
| `orch-analyst` | sonnet / high | read-only | A vague request → requirements and acceptance criteria; drift between docs and code. |
| `orch-researcher` **new** | sonnet / medium | read-only, web | Questions that need the web — libraries, standards, prior art — answered with sources. |

### Build — write code

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-dev-senior` | opus / high | code | Cross-cutting, protocol, concurrency and multi-module changes. |
| `orch-dev-middle` | sonnet / medium | code | A well-specified change inside one module. |
| `orch-dev-junior` | haiku / medium | code | Exact diffs, renames, mechanical edits. |
| `orch-frontend` **new** | sonnet / medium | code | Web UI: components, state, forms, loading/empty/error states, responsive layout. |
| `orch-mobile` **new** | opus / medium | code | iOS and Android: lifecycle, permissions, secure storage, parity between platforms. |
| `orch-db-engineer` **new** | opus / medium | migrations, queries | Schemas, safe migrations with rollback, indexes, query plans. |
| `orch-api-designer` **new** | sonnet / high | spec files only | Contracts, error model, versioning, compatibility — before the code. |
| `orch-designer` | opus / medium | styles, components | Screens, design tokens, microcopy. |

### Quality — check

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-reviewer` | opus / high | read-only | Adversarial review of every dev step: tries to refute "done", runs the build. |
| `orch-test-engineer` **new** | sonnet / medium | tests only | Missing tests, coverage gaps, flaky tests, test vectors. |
| `orch-qa` | sonnet / medium | read-only | Scenarios, smoke checklists, UX traps, false promises in the UI. |
| `orch-performance` **new** | opus / high | code | Measured optimisation: profiles, benchmarks, N+1 queries, leaks. |
| `orch-accessibility` **new** | sonnet / medium | read-only | WCAG 2.2 AA, screen readers, contrast, keyboard, text scaling. |
| `orch-build-verifier` | haiku / low | read-only | Runs the listed commands, returns PASS/FAIL with the error lines. |

### Security

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-security` | best / high | read-only | Threat model, auth, perimeter, rate limits; confirming or refuting findings. |
| `orch-protocol-reviewer` | best / high | read-only | Crypto, tokens, wire formats, cross-platform compatibility. |
| `orch-privacy-compliance` **new** | sonnet / high | read-only | Map of personal data, PII in logs, privacy policy versus actual behaviour. |
| `orch-dependency-auditor` **new** | sonnet / medium | read-only | CVEs with reachability, outdated or abandoned packages, licences. |

### Ops

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-devops` | opus / medium | infra files; production only with `OWNER_APPROVED: yes` | Snapshots, deploy plans with rollback. |
| `orch-incident-responder` **new** | opus / high | read-only | Production is broken: triage, ranked hypotheses, the cheapest safe mitigation. |
| `orch-release-manager` **new** | sonnet / medium | version, changelog; publishes only with approval | Semver bump, release notes, release checklist. |

### Support

| Agent | Model / effort | Access | Use it for |
|---|---|---|---|
| `orch-scout` | haiku / low | read-only | `file:line` maps; navigating huge documents. |
| `orch-tech-writer` | sonnet / medium | docs | README, changelogs, runbooks — every claim checked against code. |
| `orch-toolsmith` | sonnet / medium | read-only | Finds and vets plugins, skills, MCP servers and LSPs for a domain; never installs. |

When Fable is limited, every `best` role runs on Opus with effort max; when Opus is limited, senior roles move to
Sonnet with effort high (see [Per-model routing](limits-and-context.md#per-model-routing)).

## Playbooks

A playbook is a ready recipe for a kind of task: the signals that it fits, the team with models, numbered steps, a
**gate** that must hold before the next step, how to verify, a rough budget hint, typical pitfalls and an example
request. The orchestrator starts the plan from the closest playbook, drops the steps that do not apply (saying why) and
chains two when both fit — for example incident → bugfix → release. There are twelve, written out in
[`references/playbooks.md`](../../skills/orchestrator/references/playbooks.md); steps marked **[YES]** there wait for
your explicit yes. The table shows the typical shape (∥ means in parallel; the orchestrator adapts the order to the
task). The budget hint is a rough share of the 5-hour limit for an S, M or L task; it ends up in the plan's `Budget:`
line, and `costs.py --plan` shows the real number after the first wave.

| Playbook | Use it for | Typical order | Budget hint (S · M · L) |
|---|---|---|---|
| `bugfix` | A defect with a repro, a stack trace or a failing test; a regression | scout (map of the failing path) → test-engineer (failing regression test first) → dev-middle, or dev-senior if the bug crosses modules (minimal fix) → build-verifier ∥ reviewer | ≤ 2 · 2–6 · 8–15 % |
| `feature` | A new user-visible capability across two or more areas | scouts ∥ → analyst (acceptance criteria) → architect ∥ api-designer → db-engineer (migration + rollback) → backend dev ∥ frontend or mobile ∥ test-engineer → build-verifier → reviewer ∥ security and privacy-compliance (auth, personal data) ∥ accessibility (UI) → qa → tech-writer | ≤ 3 · 8–15 · 20–40 % |
| `refactor` | Restructuring without changing behaviour | scouts ∥ (callers, public surface) → test-engineer (characterization tests) → architect (L) → dev-senior in small steps, build-verifier after each → reviewer on the whole diff → tech-writer (fix paths in docs) | ≤ 3 · 5–12 · 15–30 % |
| `migration` | A database or schema change, backfill, engine switch | scout ∥ db-engineer (read-only) → architect (L) or db-engineer (expand → backfill → switch → contract) → db-engineer (forward and rollback migration, tried on a disposable DB) → dev (transition code, tests) → reviewer ∥ build-verifier → devops snapshot and plan → **your yes** → devops | ≤ 3 · 5–10 · 15–30 % |
| `dependency-upgrade` | A CVE alert, outdated majors, a runtime upgrade | dependency-auditor (risk-ordered table) → build-verifier (baseline) → researcher ∥ (breaking changes of majors) → dev-middle per package group → test-engineer → reviewer → release path with **your yes** | ≤ 2 · 4–10 · 10–25 % |
| `security-audit` | An audit, a pre-release security review, a threat model (your own systems, non-destructive) | scouts ∥ (attack surface) → security ∥ protocol-reviewer ∥ privacy-compliance ∥ dependency-auditor → dedupe → refute panel for criticals → confirmed findings fixed as bugs → reviewer round 2 → tech-writer (what was and was not checked) | 3–6 · 8–15 · 25–50 % |
| `performance` | A slow endpoint, page, query or build; high memory | scout → performance (baseline first) → hypotheses ∥ test-engineer (pinning tests) → one change at a time (performance ∥ db-engineer) → build-verifier ∥ reviewer → performance (before/after table) | ≤ 3 · 5–12 · 15–30 % |
| `incident` | Production is down or degraded right now | incident-responder ∥ devops snapshot ∥ scout (recent changes) → mitigation options with a rollback each → **your yes** → devops → incident-responder (recovery check) → root-cause fix later as a bugfix → tech-writer (postmortem) | ≤ 2 · 3–8 · 10–20 % |
| `release` | A version bump, changelog, tag, package or store publication | release-manager (version, changelog, notes) → build-verifier (full matrix) ∥ dependency-auditor → qa smoke → version files ∥ docs → exact publish commands and rollback → **your yes** → release-manager or devops | ≤ 2 · 3–8 · 8–15 % |
| `docs` | A README, runbook or API docs; docs that drifted from the code | scout → analyst (drift list) → tech-writer → build-verifier (runs every documented command, checks links) → reviewer (claims versus code) | ≤ 1 · 2–6 · 6–12 % |
| `test-coverage` | Low coverage, regressions without tests, flaky tests | build-verifier (baseline) → scout (untested modules ranked by risk) → test-engineer ∥ per module → flaky-test hunt → build-verifier ∥ reviewer | ≤ 2 · 4–10 · 10–25 % |
| `onboarding` | An inherited or unfamiliar repository | build-verifier (does it install, build, test, run?) → scouts ∥ per top-level area → analyst → architect (L) → tech-writer (project map) | ≤ 1 · 2–5 · 5–12 % |

## Example session (abridged, illustrative)

```
you      > /orchestrator:orchestrator fix the failing tests in api/ and add coverage

orch     > [limits] mode normal, fable ok, context 6%.
           Size: M (api/ only, 2 areas: handlers + tests). Playbook: bugfix. Recon first.
orch     > scout (haiku): api/ map, test commands -> .claude/orchestrator/project-map.md updated
orch     > Plan .claude/plans/2026-05-04-api-tests.md    Budget: 6% of the 5-hour limit
           1. orch-build-verifier: run `pytest api/ -x -q`, list failures        (haiku/low)
           2. orch-dev-middle: fix handlers failing in api/orders.py:40-120       (sonnet/medium)
           3. orch-test-engineer: add coverage for api/orders.py (separate file)  (sonnet/medium)   parallel with 2
           4. orch-build-verifier + orch-reviewer on both diffs                   (haiku/low, opus/high)
           Production: not touched. Continuing.
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

## Budget and spend

Every plan can carry a budget in its header, for example `**Budget:** 25%` (of the 5-hour limit) or `4M tokens`. The
orchestrator fills it in when it writes the plan, starting from the budget hint of the playbook (see
[Playbooks](#playbooks)); if you have a number in mind, name it in your request or edit the line yourself at any time.
Hints are rough, so look at `costs.py --plan` after the first wave. Spend is counted across all sessions of the project
since the plan's `Started:` time.

- `/orchestrator:costs` shows tokens and share of the limit per role and per agent, and where the budget stands.
- `/orchestrator:status` includes the budget level in its dashboard.
- A hook speaks to the orchestrator once at 80 % of the budget (prefer cheaper models, avoid optional reviews) and once
  at 100 % (launch no new agents, ask you whether to extend).

Syntax, the exact messages and the `%` versus tokens question are in
[Plan budgets](limits-and-context.md#plan-budgets); the report itself is described under
[Costs](limits-and-context.md#costs).

## Resuming

**After `/compact`, `/clear` or `claude --resume`.** The plugin's `SessionStart` hook (matcher `compact|resume|clear`)
finds the newest plan in `.claude/plans/*.md` whose header says `in-progress`, and injects its header, the
`## Checkpoint` section and a one-line limits summary into the fresh context. If the orchestrator does not continue by
itself, type `/orchestrator:resume`.

**After a restart.** A brand-new session (`startup`) does not get the checkpoint injected. Type `/orchestrator:resume`:
it reloads the checkpoint of the in-progress plan, checks the limits first and continues.

**After a limit.** In `exhausted` mode the orchestrator launches nothing, writes the checkpoint and tells you the
reset time. After the reset type `/orchestrator:resume`: failed or finished agents are continued with `SendMessage`
("Limit reset — continue from where you stopped and return the result in the agreed format."), not re-briefed.

**Asking for `/compact`.** The model cannot run `/compact`. At 75 % context it writes the checkpoint and asks you to
run it, with a keep-string such as `/compact keep: plan <path>, running agents, next step`.

A good checkpoint (template section) lists: done, in flight (agent id and what it does), next step, open decisions or
questions waiting for you, key paths. If you edit the plan by hand, keep the line `**Status:** in-progress` in the
first 4000 characters — the hook looks for it there (`checkpoint.py` accepts also the Russian words «статус» and
«чекпоинт»).

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

Details: [`references/parallelism.md`](../../skills/orchestrator/references/parallelism.md).

## Clean-context agents

For long or independent work an agent can run in a separate `claude` process that does not carry the history of the
current chat. The orchestrator does this itself when it fits; you can also do it by hand:

```bash
S=~/.claude/skills/orchestrator/scripts        # manual install; in a plugin install the scripts are inside the plugin directory

# brief from a file, background process
"$S/spawn.sh" orch-scout brief.md --mode headless --id scout-api

# brief from stdin, with a model/effort override (for example while Fable is limited)
echo "Review api/auth.py:10-120 ..." | "$S/spawn.sh" orch-reviewer - --model opus --effort max

# visible modes: terminal (macOS Terminal), tmux (session "orch"), interactive (macOS)
"$S/spawn.sh" orch-dev-middle brief.md --mode tmux

# status and results
"$S/collect.sh"                       # the 20 most recent runs
"$S/collect.sh" scout-api --wait      # wait until the run is done
"$S/collect.sh" scout-api --full      # the full result instead of the first 60 lines
```

`spawn.sh` options: `--mode headless|terminal|tmux|interactive` (default `headless`), `--id`, `--model`, `--effort`,
`--max-turns` (default 60), `--schema <file>`, `--perm acceptEdits|default|plan|auto|dontAsk|bypass` (default
`acceptEdits`), `--cwd`. Environment: `ORCH_RUNS`, `ORCH_PERM`, `ORCH_WAIT_MAX`. Results land in
`<project>/.claude/runs/<run-id>/`. The `terminal` and `interactive` modes need macOS Terminal; `tmux` needs tmux.
Proxy and `ANTHROPIC_*` variables of your shell are passed to the child through a `0600` file that is deleted after the
start. Runs started this way are counted by `costs.py --project-wide`.

## Project map

`.claude/orchestrator/project-map.md` (at most about 150 lines) is read often, so it stays short: what the project is,
components and sizes, build/test/lint commands, specs worth knowing, production facts (read-only), traps. The scout
builds it on first use; the orchestrator updates it when it goes stale. The template is
[`references/project-map-template.md`](../../skills/orchestrator/references/project-map-template.md). Commit it or
ignore it as you prefer. Do not put secrets in it: it is read often and may be committed.

## Where things live

| Path | What |
|---|---|
| `.claude/plans/YYYY-MM-DD-<slug>.md` | Plans: steps, checkpoint, budget, result. |
| `.claude/orchestrator/project-map.md` | The project map. |
| `.claude/runs/<run-id>/` | Results of `spawn.sh` runs. |
| `.claude/worktrees/` | Git worktrees of parallel writers (add to `.gitignore`). |
| `~/.claude/claude-orchestrator/` | Copy of the scripts, status-line snapshot, calibration, your optional `limits.json`, hook state. |

## Keeping costs low

- Let small tasks stay small: S tasks are done directly.
- Pass maps and ranges in briefs so expensive agents do not search.
- Prefer resuming an agent (`SendMessage`) over re-briefing a new one.
- Cheapest adequate model first; Fable/`best` only for architecture, security, protocol and critical judgement.
- Ask for compact reports; do not paste big files or full diffs into the orchestrator's chat.
- Install the status line and watch `ctx` — checkpoint early rather than compacting in a hurry.
- Use `economy` mode as a signal, not an obstacle: it exists to keep a task finishable before the window resets.
- Put a `Budget:` on big plans and look at `/orchestrator:costs` halfway: the top roles show where the spend goes, and
  the report ends with one saving tip (for example a role running on a more expensive model than its work needs).
- Rough per-agent cost guide (from
  [`references/model-routing.md`](../../skills/orchestrator/references/model-routing.md)): scout 5–50k tokens,
  build-verifier 5–30k, junior 10–30k, middle 30–100k, senior 60–500k, reviewer 40–300k, architect/protocol/security
  60–300k. A plan with five dev steps and full verification: 0.5–1.5M; a cross-platform protocol change with review
  rounds: 3–7M. These are orders of magnitude: the token totals printed by `costs.py` also count cache reads and are
  much larger, so compare roles with one another or read the ≈ % columns.

## Recipes

What to type → what happens. Each recipe works with `/orchestrator:orchestrator …` or as a plain-words request.

### 1. A small fix

```
/orchestrator:orchestrator rename the config key retryCount to maxRetries in config.py and its one usage
```

The task is size S: two files at most, an obvious change, nothing about security or production. The orchestrator makes
the change itself — no plan file, no team.

### 2. A bug with a regression test

```
/orchestrator:orchestrator after logout the session cookie stays in the browser — find the cause, fix it, add a regression test
```

Size M, playbook `bugfix`. A scout maps the failing path and the repro and test commands; if the failure cannot be
reproduced, the orchestrator asks you instead of guessing. `orch-test-engineer` writes the regression test first and
checks that it fails for the stated reason. `orch-dev-middle` — or `orch-dev-senior` when the bug crosses modules —
makes the minimal fix. `orch-build-verifier` and `orch-reviewer` then check it in parallel; a "rework" verdict goes back
to the same developer.

### 3. A new feature with a budget

```
/orchestrator:orchestrator add password reset: API endpoint, migration and a web page. Keep it under 25% of the 5-hour limit. Don't deploy.
```

Size L, playbook `feature`. Scouts map the areas, `orch-analyst` turns the request into acceptance criteria (questions
only you can answer are asked up front), `orch-architect` and `orch-api-designer` settle the design and the contract
before any code, and `orch-db-engineer` writes the migration with a rollback. Then the backend developer,
`orch-frontend` and `orch-test-engineer` work in parallel on different files (git worktrees if they share one build
tree). Review covers `orch-reviewer`, `orch-security` and `orch-privacy-compliance` (the feature touches auth and
personal data), `orch-accessibility` and `orch-qa`; `orch-tech-writer` finishes. The plan header gets `Budget: 25%`:
at 80 % a hook tells the orchestrator to prefer cheaper choices, at 100 % to launch no new agents and to ask you. "Don't
deploy" stops the plan before the production step.

### 4. A security audit

```
Use the orchestrator to audit the authentication and file-upload code of this API; confirmed findings only, with file:line and a fix
```

Playbook `security-audit` (your own systems, non-destructive). Scouts map the attack surface first. Then
`orch-security`, `orch-protocol-reviewer`, `orch-privacy-compliance` and `orch-dependency-auditor` each take one lens and
change nothing (in `economy` mode two at a time). The orchestrator deduplicates and ranks the findings; critical ones go
to a refute panel of three reviewers (accepted at two or more); confirmed ones become bugfix steps, each re-reviewed in a
second round. The report says what was checked and what was not. Requests to a deployed system and config changes wait
for your "yes".

### 5. A dependency upgrade

```
/orchestrator:orchestrator fix every npm audit finding that is reachable from our code, then move React to the latest major
```

Playbook `dependency-upgrade`. `orch-dependency-auditor` builds a table ordered by risk and effort (package, current,
target, severity, reachable or not, action); `orch-build-verifier` records a baseline on the untouched tree;
`orch-researcher` reads the changelogs of the major versions and attaches the sources. Then `orch-dev-middle` goes group
by group — patches and minors first, then one major per step — with a build check after each, `orch-test-engineer`
covers behaviour the upgrade showed to be untested, and `orch-reviewer` checks the lockfile diff. Deploying goes through
your normal release path and needs your "yes".

### 6. A production incident

```
Checkout returns 502 since 14:20. Find out why and propose the safest fix; ask me before changing anything on the server
```

Playbook `incident`. `orch-incident-responder` triages — what fails, since when, for whom, what changed — while
`orch-devops` takes a read-only snapshot and a scout lists recent changes. They offer mitigation options, cheapest safe
one first, each with a rollback, and the orchestrator stops for your explicit "yes". Only then does `orch-devops` get a
brief with `OWNER_APPROVED: yes` and the exact action list; anything extra, such as a second restart, stops and asks
again. The responder checks the recovery, the root-cause fix follows later as a bugfix, and `orch-tech-writer` drafts a
blameless postmortem.

### 7. An unfamiliar codebase

```
I inherited this repo. Explain what it does, how to run it and what is risky. Don't change anything.
```

Playbook `onboarding`. `orch-build-verifier` first checks whether the project installs, builds, tests and runs,
recording PASS or FAIL and fixing nothing. Scouts map each top-level area in parallel; `orch-analyst` lists
contradictions between docs and code, risky spots and open questions; `orch-tech-writer` writes
`.claude/orchestrator/project-map.md` (about 150 lines at most) from the commands that were really run — the starting
point for every later task.

### 8. Pick up where you left off

```
/orchestrator:status
/orchestrator:costs
/orchestrator:resume
```

`status` shows where the plan stands and what is running; `costs` shows what it has cost so far and where the budget
stands; `resume` reloads the checkpoint after `/compact`, `/clear`, a restart or a limit reset and carries on, resuming
finished or failed agents with `SendMessage` instead of re-briefing them.

## Update, uninstall

**Update.** In Claude Code: `/plugin marketplace update claude-orchestrator`, then
`/plugin update orchestrator@claude-orchestrator` (or use the `/plugin` menu). From a terminal:
`claude plugin update orchestrator@claude-orchestrator`. Manual install: `git pull && ./install.sh` with the same
flags as before.

**Uninstall.** First type `/orchestrator:setup remove` — it removes the status line entry, restores your previous
status line (your data and `limits.json` stay in `~/.claude/claude-orchestrator`; delete that folder by hand for a
clean slate). Then
`/plugin uninstall orchestrator@claude-orchestrator` (terminal: `claude plugin uninstall orchestrator@claude-orchestrator`).
Optionally `/plugin marketplace remove claude-orchestrator`. If you forgot the first step, delete the `statusLine`
entry in `~/.claude/settings.json` (a backup was made at setup) or run `./uninstall.sh` from a clone of the repository.
Manual installs: `./uninstall.sh` (or `./uninstall.sh --project <dir>`) removes the skill, the `orch-*` agents,
`~/.claude/claude-orchestrator` and only our status line and hook entries, and restores the previous status line.

## Migrating from v1

Version 2.0.0 renamed the product, so the names changed everywhere:

| | v1 | 2.0 |
|---|---|---|
| Product | Team Orchestrator | Claude Orchestrator |
| Plugin | `team-orchestrator` | `orchestrator` |
| Marketplace | `team-orchestrator` | `claude-orchestrator` |
| Main command | `/team-orchestrator` (`/team-orchestrator:team-orchestrator`) | `/orchestrator:orchestrator` (manual install: `/orchestrator`) |
| Short commands | `/team-orchestrator resume` | `/orchestrator:status`, `:limits`, `:costs`, `:resume`, `:setup` |
| Agents | 15, `team-orchestrator:orch-<role>` | 27, `orchestrator:orch-<role>` |
| Data directory | `~/.claude/team-orchestrator/` | `~/.claude/claude-orchestrator/` |

**Plugin install.**

```
/plugin uninstall team-orchestrator@team-orchestrator
/plugin marketplace remove team-orchestrator
/plugin install orchestrator --marketplace newzealandgrom/claude-orchestrator
```

If you had enabled the status line, type `/orchestrator:setup` once more: it points `settings.json` at the new
directory and keeps the status line you chained behind the old one.

**Manual install.** Pull the new version and run `./install.sh` with the flags you used before. It removes the old
`skills/team-orchestrator` folder and, if `settings.json` still has v1 status line or hook entries, migrates them to
the new version automatically (a backup is made first and your own chained status line stays).
`./uninstall.sh` of the new version cleans up v1 leftovers too.

**Data.** Your plans in `.claude/plans/` and the project map `.claude/orchestrator/project-map.md` keep working as they
are. The new scripts read an old `limits.json` and an old status-line snapshot from `~/.claude/team-orchestrator/` as a
fallback, but write only to `~/.claude/claude-orchestrator/`; calibration starts from scratch. When you are done, copy
a `limits.json` you want to keep to the new directory and delete the old one. More in
[Migrating from v1](limits-and-context.md#migrating-from-v1).

## Troubleshooting

**The `/orchestrator:…` commands are not found.** Type `/reload-plugins` or restart Claude Code, then check `/plugin` →
"Installed". On a Claude Code older than 2.1.275 the one-line install fails — use the two-step form from
[Install](#install).

**`/agents` shows fewer than 27 agents.** An older version is installed; update it (see
[Update, uninstall](#update-uninstall)).

**The orchestrator did the task alone, without a team.** The task was sized S (two files at most, obvious fix, no
security, protocol or production). That is by design.

**No `5h` / `7d` in the status line, or no status line at all.** See [Troubleshooting](limits-and-context.md#troubleshooting)
in the limits guide.
