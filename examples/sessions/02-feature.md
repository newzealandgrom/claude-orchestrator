# Session 2: a feature (password reset by e-mail)

The [feature playbook](../../skills/orchestrator/references/playbooks.md) on a generic Node/Express + React app, with the limit features at work: economy mode, a budget warning, a context checkpoint and a `/compact` recovery. The plan at the halfway point is [plan-feature.md](../plan-feature.md); the matching reports are [limits.txt](../outputs/limits.txt), [costs.txt](../outputs/costs.txt) and [status.txt](../outputs/status.txt). Names, ids and numbers are illustrative; hook and report texts have the real formats.

## The request

```text
/orchestrator:orchestrator Add 'forgot password' by e-mail: the user enters their address, gets a link valid for 30 minutes and sets a new password on a new page. Backend API, DB migration, web client, e-mail template. Keep it under 25% of my 5-hour limit. Don't deploy anything without asking me.
```

## 1. Gate, size, plan

- `limits.py` → `mode: NORMAL`, Fable `ok`, context 3 %. Size **L**: a new feature, an auth flow, four areas (API, DB, web, mail), production at the end. L means the full cycle with a second opinion before any code.
- The playbook supplies the team and the order. The user sees the plan in ten lines and nothing blocks, because the only irreversible step is the last one:

```text
Plan .claude/plans/2026-05-04-password-reset.md   feature · L · Budget: 25% of the 5-hour limit (estimate ≈ 20%)
1 recon: 3 scouts + test baseline              haiku/low, in parallel
2 design review of the reset flow              security, best/high
3 backend core: migration, tokens, mailer      dev-senior, opus/high
4 verify step 3                                build-verifier ∥ 2 reviewers
5 endpoints + web pages ∥ 6 docs + e-mail copy dev-senior ∥ tech-writer
7 integration + e2e tests                      test-engineer, sonnet/medium
8 final verification                           build-verifier, reviewer, security, accessibility, qa
9 production gate: needs your explicit yes     devops
```

## 2. Steps 1 to 4 (normal mode)

- **Step 1.** Three scouts (routes, DB and migrations, web and mail) and a build-verifier baseline go out in one message: `npm test` 212 passed, `npm run lint` clean. The project map is refreshed.
- **Step 2.** No architect: the only open risk is the auth flow, so the second-opinion seat goes to `orch-security` (`best`; Fable is available, so it runs on Fable). Six numbered corrections S1 to S6 come back: hash the token at rest, 30-minute expiry with atomic single use, identical answers for known and unknown addresses, rate limits per address and per IP, revoke sessions after a reset, token in the URL fragment. The orchestrator copies them into every brief.
- **Step 3.** `orch-dev-senior` (Opus: security-sensitive, everything builds on it) writes the migration with rollback, the token service and the mailer method. No db-engineer: an additive table without backfill. Up → down → up passes on a disposable database.
- **Step 4.** Build-verifier plus two reviewers (code, migration) in parallel. The code reviewer says REWORK: `consume()` reads and then updates, so two concurrent requests can use one token (`src/services/resetTokens.js:41-58`); the mailer logs the full reset URL at debug level (`src/services/mailer.js:52`). Both findings go in one `SendMessage` to the same dev-senior; the reviewer re-checks only the fixes: ACCEPT. The migration reviewer accepted at once.

## 3. The limits hook switches to economy

Steps 5 and 6 are launched in one message (disjoint files). The PostToolUse hook then speaks, because the state changed:

```text
[orchestrator limits] mode=economy session=63% week=22% context=41% models=fable:economy,haiku:ok,opus:ok,sonnet:ok :: ECONOMY: max 2 parallel heavy agents; … | FABLE ECONOMY: …
```

The session crossed 60 % a little earlier; the hook speaks after the next agent call, hence 63 %. Part of that is other windows on the same account. What changes for the rest of the run:

- At most two heavy (Opus or Fable) agents at once. One is running now, so nothing is blocked; step 8 will need exactly two.
- Fable only as a judge: step 8's `orch-security` will run as `model: opus, effort: max`.
- Haiku for search and builds (already so), no refute panels (none planned), reviews only for risky diffs, questions to an agent batched into one message.

Halfway, the user types `/orchestrator:status` (first lines below, full text in [outputs/status.txt](../outputs/status.txt)) and `/orchestrator:costs`:

```text
[orchestrator] status — plan .claude/plans/2026-05-04-password-reset.md (in-progress)
progress: 4 done · 2 in progress · 3 to do  ■■■■◧◧□□□ 44%
```

> 18.4 % of the 5-hour limit (about 3.4 % of the week) after 4 of 9 steps: 74 % of the 25 % budget. The orchestrator's own context is the biggest line (42 %), then dev-senior (31 %) and the reviewers (16 %). Nothing to cut yet; the cheap habits are already in use (reading is delegated, checkpoints are early).

## 4. The budget hook

Step 5 finishes. When the orchestrator launches step 7, the budget hook speaks:

```text
[orchestrator budget] plan .claude/plans/2026-05-04-password-reset.md: 82% of the budget (25% of the 5-hour limit) spent. Prefer cheaper models, avoid optional reviews and scope growth; tell the user if the rest will not fit.
```

The rest (tests, final checks, deploy) is estimated at about 5 %, the budget has 4.5 % left, so the orchestrator tells the user instead of silently overrunning:

> 82 % of the 25 % budget is spent and the rest will not fit. Options: (a) raise the budget to 30 %; (b) keep 25 % and drop the accessibility pass and the second security look; (c) stop after the tests. I recommend (a).

The user answers "a". The orchestrator edits the header to `Budget: 30% of the 5-hour limit` and goes on.

## 5. Context at 75 %

At 52 % the hook had asked for a checkpoint; the orchestrator rewrote the plan's `## Checkpoint` and stopped reading files itself. Now the context is at 75 %, so it refreshes the checkpoint (done: steps 1 to 6; in flight: test-engineer `5c19e7a0d2`; next: step 8; open decisions: none) and asks, because only the user can run `/compact`:

> My context is at 75 %. The plan checkpoint is current. Please run:
> `/compact keep: plan .claude/plans/2026-05-04-password-reset.md, running agents, next step`

After the compaction the SessionStart hook (source `compact`) puts the plan header, the Checkpoint section and one limits line back into the fresh context:

```text
[orchestrator limits] mode=economy session=66% week=22% context=9% models=fable:economy,haiku:ok,opus:ok,sonnet:ok :: ECONOMY: …
```

The user types `/orchestrator:resume`. The orchestrator re-reads the plan, runs the limits gate, collects the test-engineer's report (it finished while the context was being compacted) and continues. Nothing was re-briefed.

## 6. Steps 7 and 8

- **Step 7.** `test/auth.reset.test.js` (14 tests) and `test/e2e/reset.spec.ts` (3 scenarios). `npm test` → 231 passed (212 at baseline, plus 5 service tests from step 3 and these 14), `npm run test:e2e` → 3 passed. With token reuse deliberately allowed, 2 of the new tests fail, so they do prove something.
- **Step 8** is one message with five agents, two of them heavy as economy allows: `orch-build-verifier`, `orch-reviewer`, `orch-accessibility`, `orch-qa`, and the security pass launched as `Agent(subagent_type: "orch-security", model: "opus", effort: "max")` because Fable is in economy.
  - build-verifier PASS: tests 231, lint 0, web build OK. qa: six scenarios pass.
  - reviewer ACCEPT, but a doc claim is wrong: `docs/api/auth.md` says the link is valid for 60 minutes, the code and S2 say 30.
  - security: confirms S1 to S6, with one HIGH: the rate limiter keys on the raw address, so the same address in a different letter case gets its own bucket and S4 can be bypassed (`src/routes/auth.js:131`).
  - accessibility: two MEDIUM: the error text is not tied to the field (`ResetPassword.tsx:63`), the success message is not announced (`ForgotPassword.tsx:41`).
- **Rework, batched.** One `SendMessage` to dev-senior `a3de429a5d` (normalise the address; the two a11y fixes) and one to tech-writer `b81f6c0e47` (30 minutes). Round 2 re-checks only the security-relevant fix. The a11y fix is covered by a new e2e assertion instead of a second accessibility review (economy: reviews only for risky diffs). ACCEPT.

## 7. Production gate (step 9)

`orch-devops` first takes a read-only snapshot: app version, migrations up to date, health OK, backup age 3 h, sessions live in the database (a restart logs nobody out). The orchestrator then shows the plan and stops:

> 1. Back up the database (timestamped, UTC). 2. Apply `20260504_password_reset_tokens.sql` (new table only). 3. Deploy the new build (about 5 s restart). 4. Smoke checks: health endpoint, one reset mail to your test mailbox. Rollback: `npm run migrate:down` and redeploy the previous build. Say "yes" to proceed.

The user says "yes". Only now `orch-devops` gets a brief with `OWNER_APPROVED: yes` and exactly those four actions; anything else is forbidden. Post-checks pass: health OK, migration applied, the test mail arrived, no new errors in the logs.

## 8. Report to the user

The plan's Result section takes the spend from `python3 scripts/costs.py --plan .claude/plans/2026-05-04-password-reset.md`:

```text
budget (2026-05-04-password-reset.md, all sessions since 2026-05-04 16:50): 30% of the 5-hour limit → spent 23.1% = 77% → OK
```

> **Password reset by e-mail is built, verified and deployed.**
> Changed: migration `20260504_password_reset_tokens.sql`; `src/services/resetTokens.js`, `src/services/mailer.js`; two endpoints in `src/routes/auth.js`; pages `/forgot-password` and `/reset-password`; e-mail template; `docs/api/auth.md`; 22 new tests.
> Verified: `npm test` 231 passed, `npm run test:e2e` 3 passed, lint and web build clean; reviewer, security (round 2) and qa accepted; production health OK, one real reset mail delivered.
> Not verified: deliverability with real providers beyond the test mailbox; a manual screen-reader pass.
> For you: watch the first real resets; an expired-token cleanup job is optional (the table has an index for it).
> Cost: about 23 % of the 5-hour limit (budget 30 %, estimate was 20 %).

## What to notice

- Hooks spoke only when the state changed; the user decided about money (the budget) while the orchestrator decided about method (economy, batching).
- The plan file, not the chat, carried the state: `/compact` lost nothing.
- Fable-only seats became Opus with maximum effort; reviews narrowed to the risky diff; rework was batched.
- Nothing was deployed before the "yes", and the devops brief listed the exact actions.
