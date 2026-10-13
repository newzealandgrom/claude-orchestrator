# Playbooks

## How to use
1. Pick the closest playbook; if two apply, chain them (incident → bugfix → release).
2. Copy its **Team** and **Steps** into `.claude/plans/YYYY-MM-DD-<slug>.md` (`templates/plan.md`); set `Playbook:`.
3. Adapt: drop steps that do not apply (say why); add `file:line` ranges and a verify command per step.
4. Set `Budget:` from the hint (% of the 5-hour limit, e.g. `25%`, or `4M tokens`) and `Started:`; hints are rough, re-check with `costs.py --plan`.
5. Roles are the `orch-<role>` agents, grouped by `model/effort`; `best` = Fable if available, else Opus. `∥` parallel · **gate** must hold before the next step · **[YES]** needs the user's explicit yes.
6. Run the limits gate before every wave; Fable off → `best` roles on Opus, effort max. S tasks: no playbook.

## 1. Bugfix
**Signals:** defect with a repro or stack trace; regression; 1–3 modules.
**Team:** haiku/low: scout, build-verifier · sonnet/medium: test-engineer, dev-middle · opus/high: reviewer, dev-senior (if cross-module) · best/high: security (auth, data exposure).
**Steps:**
1. scout: `file:line` map of the failing path, repro and test commands. Gate: repro fails as reported (else ask, don't guess).
2. test-engineer: failing regression test. Gate: fails for the stated reason.
3. dev: minimal fix, listed files only. Gate: new test green, nothing else touched.
4. build-verifier (suite, lint, types) ∥ reviewer. Gate: PASS + ACCEPT; REWORK → same dev via `SendMessage`, reviewer re-checks fixes only.
5. Hotfix to prod: devops snapshot → plan with rollback → **[YES]** → devops (`OWNER_APPROVED: yes`).
**Verify:** repro passes; new test fails on old code; build-verifier PASS; reviewer ACCEPT.
**Budget hint:** S ≤ 2% · M 2–6% · L 8–15%.
**Pitfalls:** fixing the symptom (reviewer tries neighbouring inputs); a test that never failed.
**Example:** "After logout the session cookie stays in the browser. Find the cause, fix it, add a test."

## 2. Feature
**Signals:** new capability across ≥ 2 areas (API, DB, UI, mail, mobile); vague acceptance criteria.
**Team:** haiku/low: scouts, build-verifier · sonnet/high: analyst, api-designer, privacy-compliance · sonnet/medium: frontend, test-engineer, qa, accessibility, tech-writer · opus/high: dev-senior, reviewer · opus/medium: db-engineer, mobile · best/high: architect (security takes this seat for an auth-only flow), security.
**Steps:**
1. scouts ∥ per area: maps, build/test commands. Gate: `file:line` anchors per area.
2. analyst: scope, non-goals, testable acceptance criteria, questions with defaults. Gate: user-only questions asked now.
3. architect ∥ api-designer: design, contract (endpoints, errors, idempotency), data model, rollout. Gate: corrections resolved; user sees a 5–12 line summary.
4. db-engineer: migration + rollback on a disposable DB. Gate: up → down → up passes.
5. backend dev ∥ frontend/mobile ∥ test-engineer; one writer per file, worktrees for a shared build tree. Gate: areas build, own tests green.
6. build-verifier (merged tree) → reviewer per dev step ∥ security, privacy-compliance (auth, PII) ∥ accessibility (UI) → qa ∥ tech-writer (docs). Gate: ACCEPT everywhere.
7. devops snapshot → plan → **[YES]** → devops. Shared-database migrations always wait.
**Verify:** every acceptance criterion has a test; build-verifier (merged tree), reviewer per dev step, qa; protocol-reviewer if a wire format changed.
**Budget hint:** S ≤ 3% · M 8–15% · L 20–40%.
**Pitfalls:** coding before the contract is frozen; parallel writers on one build tree.
**Example:** "Add 'forgot password' by e-mail: API, migration, web page, e-mail template. Don't deploy."

## 3. Refactor
**Signals:** behaviour-preserving restructure: split a file, rename a module, replace a pattern.
**Team:** haiku/low: scouts, build-verifier · haiku/medium: dev-junior (exact edits) · sonnet/medium: test-engineer · opus/high: dev-senior, reviewer · best/high: architect (L).
**Steps:**
1. scouts ∥: callers, public surface, dynamic references (strings, configs, docs). Gate: complete caller list.
2. test-engineer: characterization tests around the code that will move. Gate: green on unchanged code.
3. architect (L, else orchestrator): small ordered steps, each building and passing alone. Gate: steps in the plan.
4. dev-senior, one step at a time (junior for pure renames); build-verifier after each. Gate: same tests green.
5. reviewer on the whole diff: "behaviour and public API unchanged". Gate: ACCEPT. No **[YES]** step; if the public API must change, stop and ask.
**Verify:** suite before = after; types, lint; API diff; reviewer ACCEPT.
**Budget hint:** S ≤ 3% · M 5–12% · L 15–30%.
**Pitfalls:** behaviour change hidden in a refactor step; two writers on the monolith.
**Example:** "Split the 3,000-line OrdersController into services; behaviour and API unchanged."

## 4. Migration (database/schema)
**Signals:** schema change, backfill, column type change, big-table index, ORM/engine switch.
**Team:** haiku/low: scout, build-verifier · sonnet/medium: dev-middle, test-engineer · opus/medium: db-engineer, devops · opus/high: reviewer · best/high: architect (L).
**Steps:**
1. scout ∥ db-engineer (read-only): schema, models, queries per table, row counts. Gate: callers and sizes known (else ask for production counts).
2. architect (L) or db-engineer: expand → batched backfill → switch reads → contract later. Gate: every phase works with the previous app version and has a rollback.
3. db-engineer: forward + rollback migration on a disposable DB with realistic volume. Gate: up → down → up passes; lock-time estimate.
4. dev: transition code (dual-write, read fallback) + tests; reviewer ∥ build-verifier on the migrated DB. Gate: tests pass on old and new schema; ACCEPT.
5. devops read-only snapshot (version, size, backup age) → plan: backup, order, rollback command, expected lock. Gate: plan shown.
6. **[YES]** → devops (`OWNER_APPROVED: yes`); post-checks: row counts, constraints, health. The destructive "contract" phase is a separate step with its own **[YES]**.
**Verify:** up/down on a copy; row counts before/after; tests on both schemas; reviewer + build-verifier.
**Budget hint:** S ≤ 3% · M 5–10% · L 15–30%.
**Pitfalls:** one-transaction backfill locking a big table; expand and drop in one release.
**Example:** "Split users.full_name into first/last name on a 20M-row table, no downtime. Show the plan first."

## 5. Dependency upgrade
**Signals:** CVE alert, outdated majors, runtime upgrade, abandoned package.
**Team:** haiku/low: build-verifier · sonnet/medium: dependency-auditor, researcher, dev-middle, test-engineer · opus/high: reviewer.
**Steps:**
1. dependency-auditor: lockfile inventory, audit tools, reachability, licences. Gate: table `package | current | target | severity | reachable? | action` by risk × effort.
2. build-verifier: baseline on the untouched tree. Gate: existing failures recorded.
3. researcher ∥ (majors only): breaking changes from changelogs, with URLs. Gate: sources attached.
4. dev-middle per package group: patches/minors first, then one major per step; test-engineer covers untested behaviour. Gate: PASS vs baseline.
5. reviewer: lockfile and code diff (new transitive packages, install scripts, licences); auditor re-run. Gate: ACCEPT, audit shows the fixed set. Deploy via the normal release path: **[YES]**.
**Verify:** audit before/after; full tests; reviewer on the lockfile diff.
**Budget hint:** S ≤ 2% · M 4–10% · L 10–25%.
**Pitfalls:** everything at once (cannot bisect); blind `audit fix --force`.
**Example:** "Fix every npm audit finding reachable from our code, then move React to the latest major."

## 6. Security audit
**Signals:** "audit", "pentest", pre-release security review, threat model. Own systems only, non-destructive.
**Team:** haiku/low: scouts · sonnet/high: privacy-compliance · sonnet/medium: dependency-auditor, tech-writer · opus/high: reviewer · opus/medium: devops (read-only) · best/high: security, protocol-reviewer.
**Steps:**
1. scouts ∥ per area: attack-surface map (entry points, auth, secrets, data stores, trust boundaries). Gate: scope fully mapped.
2. security ∥ protocol-reviewer ∥ privacy-compliance ∥ dependency-auditor, one lens each. Gate: each returns severity, `file:line`, scenario, fix, "not verified".
3. Orchestrator dedupes and ranks. Gate: one list, one owner per finding.
4. Critical → refute panel: 3 independent reviewers, different lenses (code path, local repro, deployed config via devops); accept at ≥ 2 "not refuted". High → one reviewer re-derives it. Economy: one `best` judge instead.
5. Confirmed findings → bugfix steps by severity; round 2 (reviewer + original lens) on every security fix. Requests to a deployed system, config changes: **[YES]**.
6. tech-writer: what was checked and what was not. Gate: claims backed by `file:line`.
**Verify:** each confirmed finding has a repro or `file:line`; criticals passed the refute panel; reviewer round 2 on fixes.
**Budget hint:** S 3–6% · M 8–15% · L 25–50%.
**Pitfalls:** scope not authorised; a fix that opens a new bypass; "secure" instead of "nothing found in what was checked".
**Example:** "Audit this API's auth and file-upload code; confirmed findings only, with file:line and a fix."

## 7. Performance
**Signals:** slow endpoint, page, query or build; high memory; timeouts under load.
**Team:** haiku/low: scout, build-verifier · sonnet/medium: frontend, test-engineer · opus/high: performance, dev-senior, reviewer · opus/medium: db-engineer.
**Steps:**
1. scout: hot-path candidates, how to run benchmarks and profilers. Gate: a repeatable measurement command exists (else performance builds one).
2. performance: baseline, ≥ 3 runs with variance; target agreed with the user (e.g. p95 < 300 ms). Gate: numbers in the plan; no change before this.
3. performance: hypotheses ranked by profile evidence ∥ test-engineer: tests pinning current behaviour. Gate: top 3 with expected gain.
4. performance ∥ db-engineer (queries, indexes; separate files): one change at a time, same measurement. Gate: gain beyond noise, else revert.
5. build-verifier (tests + benchmark) ∥ reviewer (cache invalidation, races, leaks); performance: before/after table. Gate: ACCEPT; target met or reason documented. No **[YES]** unless deployed.
**Verify:** same command before/after (runs, variance); full suite; reviewer ACCEPT.
**Budget hint:** S ≤ 3% · M 5–12% · L 15–30%.
**Pitfalls:** no baseline; optimising cold code; different data or machine between runs.
**Example:** "The /reports endpoint takes 8 s for 1M rows. Bring p95 under 1 s; show before/after."

## 8. Incident
**Signals:** production is down or degraded now; error spike; alert fired.
**Team:** opus/high: incident-responder, dev-senior, reviewer · opus/medium: devops (read-only first) · haiku/low: scout · sonnet/medium: tech-writer.
**Steps:**
1. incident-responder ∥ devops snapshot ∥ scout (recent changes): what fails, since when, for whom, what changed. Gate: 3-line status, ranked hypotheses with timestamps, secrets and personal data masked.
2. Mitigation options, cheapest safe first (rollback, flag off, scale, failover), each with risk and undo. Gate: exact commands plus rollback shown to the user; a public status text also needs **[YES]**.
3. **[YES]**; devops runs only the approved list (`OWNER_APPROVED: yes`); anything extra (e.g. a second restart) stops and asks again. The gate holds in a fire too.
4. incident-responder verifies recovery (error rate, health, logs, one more window). Gate: back to baseline. Root-cause fix later as a bugfix; its deploy needs **[YES]**.
5. tech-writer: blameless postmortem (timeline, cause, what worked, follow-ups). Gate: every claim has a log line or commit.
**Verify:** health, error rate, logs before/after; deployed hashes equal local; incident-responder re-check.
**Budget hint:** S ≤ 2% · M 3–8% · L 10–20%.
**Pitfalls:** changing production without the yes "because it is urgent"; several changes at once.
**Example:** "Checkout returns 502 since 14:20. Find why and propose the safest fix; ask before touching the server."

## 9. Release
**Signals:** cut a release, bump a version, changelog, tag, package or store publication.
**Team:** sonnet/medium: release-manager, qa, dependency-auditor, tech-writer · haiku/low: build-verifier · opus/high: reviewer · opus/medium: devops.
**Steps:**
1. release-manager: `git log <last-tag>..HEAD` → version (state the semver rule), changelog, release notes, a migration note per breaking change. Gate: no breaking change without a note.
2. build-verifier (full matrix on the release commit) ∥ dependency-auditor (CVEs, licences). Gate: all PASS, known failures listed.
3. qa: smoke checklist on built artifacts: fresh install, upgrade from the previous version, main flows. Gate: pass or conscious deferrals.
4. release-manager: version files and CHANGELOG only (no tag, no push) ∥ tech-writer: docs. Gate: reviewer confirms version strings agree.
5. Show exact commands (tag, push, publish) and rollback. **[YES]**; release-manager or devops (`OWNER_APPROVED: yes`) runs only those, then verifies a fresh install of the published artifact. Announcements: **[YES]**.
**Verify:** versions agree in all files; changelog matches `git log`; tests green on the tag; secret scan; reviewer on version strings.
**Budget hint:** S ≤ 2% · M 3–8% · L 8–15%.
**Pitfalls:** guessing the bump rule; publishing unscanned files; tagging a dirty tree.
**Example:** "Prepare release 2.4.0 (version, changelog, migration notes, checks). Show the publish commands; don't run them."

## 10. Docs
**Signals:** README, API docs, runbook, architecture overview, changelog; docs drifted from code.
**Team:** haiku/low: scout, build-verifier · sonnet/high: analyst (drift) · sonnet/medium: tech-writer · opus/high: reviewer.
**Steps:**
1. scout: what is real (entry points, commands, config/env names, public API as `file:line`, existing docs); analyst (old docs only): docs-vs-code contradictions. Gate: map, drift list, files to touch.
2. tech-writer: edits only the listed files; each claim traced to code, unverifiable ones marked. Gate: no invented flags, commands, outputs.
3. build-verifier: run every documented command and sample from a clean state; check relative links. Gate: PASS, broken items listed.
4. reviewer: tries to refute a sample of claims plus every security, limit and performance claim. Gate: ACCEPT. No **[YES]** step.
**Verify:** samples executed; links resolve; no secrets or personal paths; reviewer refutation pass.
**Budget hint:** S ≤ 1% · M 2–6% · L 6–12%.
**Pitfalls:** promises like "zero-logs" the code does not keep; documenting intent instead of behaviour.
**Example:** "Write a README (install, configuration, troubleshooting) that matches what the code really does."

## 11. Test coverage
**Signals:** low coverage, untested regressions, flaky tests, legacy code with no safety net.
**Team:** haiku/low: build-verifier, scout · sonnet/medium: test-engineer, dev-middle (only for seams the brief allows) · opus/high: reviewer.
**Steps:**
1. build-verifier: baseline: suite and coverage command, failing and flaky tests. Gate: numbers in the plan.
2. scout: untested modules ranked by risk (money, auth, data loss, parsing) and the test conventions. Gate: priorities confirmed (ask if unclear).
3. test-engineer ∥ per module: criteria first, then edges (empty, huge, unicode, errors, permissions); deterministic only. Gate: pass now, fail when behaviour is broken (spot-check). Product bugs stay expected-fail with the reason and become bugfix steps.
4. test-engineer: flaky hunt, repeat suspicious tests; fix the test if the flakiness is in the test. Gate: stable over repeated runs.
5. build-verifier (suite, coverage) ∥ reviewer (asserts behaviour not implementation; no sleeps, no network). Gate: ACCEPT, coverage delta reported. No **[YES]** step.
**Verify:** suite and coverage before/after; new tests fail on a deliberately broken implementation; reviewer ACCEPT.
**Budget hint:** S ≤ 2% · M 4–10% · L 10–25%.
**Pitfalls:** chasing the percentage with assertion-free tests; fixing product bugs inside a test task.
**Example:** "Add tests for the billing module (proration, refunds) and fix the flaky tests from the CI log."

## 12. Onboarding (unknown codebase)
**Signals:** inherited or unfamiliar repo, no docs, first run in a project (no `.claude/orchestrator/project-map.md`).
**Team:** haiku/low: build-verifier, scouts · sonnet/high: analyst · sonnet/medium: tech-writer, toolsmith, researcher (unfamiliar stack) · best/high: architect (L).
**Steps:**
1. build-verifier: does it install, build, test, lint, run? Commands from README, CI, package files. Gate: each recorded PASS/FAIL; nothing is fixed.
2. scouts ∥ per top-level area (≤ 6): structure, entry points, data stores, external services, config/env names (never values). Gate: one-page `file:line` map each.
3. analyst: docs-vs-code contradictions, risky spots, questions with defaults; architect (L): one-page assessment (components, data flow, risks, first tasks). Gate: user reads it.
4. tech-writer: `.claude/orchestrator/project-map.md` from `references/project-map-template.md`, ≤ 150 lines, commands from step 1. Gate: no secrets, no invented facts.
5. Unfamiliar stack: toolsmith ∥ researcher, ≤ 3 plugins/LSP/skills with sources; the user installs, never the agent. No **[YES]** step.
**Verify:** every command in the map was run; every path exists.
**Budget hint:** S ≤ 1% · M 2–5% · L 5–12%.
**Pitfalls:** reading the monolith in the orchestrator's own context; copying `.env` values.
**Example:** "I inherited this repo. Explain what it does, how to run it, what is risky. Change nothing."
