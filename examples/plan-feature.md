# Plan: Password reset by e-mail

**Date:** 2026-05-04 · **Status:** in-progress
**Started:** 2026-05-04 16:50 · **Budget:** 25% of the 5-hour limit
**Playbook:** feature
**Request (verbatim):** "Add 'forgot password' by e-mail: the user enters their address, gets a link valid for 30 minutes and sets a new password on a new page. Backend API, DB migration, web client, e-mail template. Keep it under 25% of my 5-hour limit. Don't deploy anything without asking me."
**Size:** L · **Token estimate:** ≈ 9M units (≈ 20% of the 5-hour limit) · **Actual:** —
**Touches production / publishes:** yes (step 9: migration + deploy, only after the user's yes)
**Limits at start:** `python3 <skill>/scripts/limits.py` → mode normal, fable ok, context 3%

## Goal and scope
A user who forgot the password can request a reset link by e-mail (valid 30 minutes, single use) and set a new password on a new page. At the end: the old password stops working, every existing session of that account is revoked, and the flow never reveals whether an address is registered.
In scope: 2 API endpoints, 1 DB table, 2 web pages, 1 e-mail template, API docs. Out of scope: SMS or 2FA reset, admin-initiated reset, password-strength policy, localisation of the e-mail, mobile apps.

## Recon (facts with sources)
- `src/routes/auth.js:18-96` — register, login, logout; no reset routes yet. Rate limiting is per route and per IP (`src/middleware/rateLimit.js:5-30`).
- `db/migrations/` — plain SQL files, `npm run migrate` / `npm run migrate:down`; the `sessions` table has a `user_id` column.
- `src/services/mailer.js:1-58` — one `sendMail({to, subject, text, html})` over SMTP; `MAIL_TRANSPORT=stub` captures mail in tests.
- `web/src/pages/Login.tsx:61` — the "Forgot password?" link is a dead `#`.
- Commands: `npm test` (212 tests, green at baseline), `npm run lint`, `cd web && npm run build`, `npm run test:e2e`.
- Design review (step 2): S1 store only a SHA-256 hash of the token. S2 30-minute expiry, single use enforced atomically in SQL. S3 same response and similar timing for known and unknown addresses. S4 rate limit 5 requests per hour per address and per IP. S5 revoke all sessions of the user after a reset and notify by e-mail. S6 token travels in the URL fragment, is removed from history and sent in the POST body; `Referrer-Policy: no-referrer` on the reset page.

## Steps
| # | Status | What | Files | Agent (model/effort) | Depends on | Parallel with | Done when | Verify |
|---|---|---|---|---|---|---|---|---|
| 1 | [x] | Recon: auth routes, DB, mailer, web pages; baseline of tests and lint | `src/routes/auth.js`, `db/migrations/`, `src/services/mailer.js`, `web/src/pages/` | 3× orch-scout (haiku/low) ∥ orch-build-verifier (haiku/low) | — | — | 3 maps with `file:line`; project map updated; baseline recorded | `npm test`, `npm run lint` → 212 passed, 0 errors |
| 2 | [x] | Design review of the reset flow (token model, API contract, limits, e-mail) as a second opinion before code; security instead of architect because the only open risk is the auth flow | Goal and scope above | orch-security (best/high, ran on Fable) | 1 | — | corrections S1–S6 resolved and copied into the briefs | — |
| 3 | [x] | Backend core: migration with rollback, token service, mailer method (no db-engineer: additive table, no backfill) | `db/migrations/20260504_password_reset_tokens.sql` (new), `src/services/resetTokens.js` (new), `src/services/mailer.js:40-58` | orch-dev-senior (opus/high), id f6b3e1a924 | 2 | — | migration up → down → up passes on a disposable DB; service tests green | `npm run migrate && npm run migrate:down && npm run migrate && npm test -- resetTokens` |
| 4 | [x] | Verify the backend core | same files | orch-build-verifier (haiku/low) ∥ 2× orch-reviewer (opus/high): code, migration | 3 | — | PASS; both ACCEPT after one rework round | `npm test`, `npm run lint` |
| 5 | [~] | Endpoints `POST /auth/password-reset` and `POST /auth/password-reset/confirm`, then web pages `/forgot-password` and `/reset-password`; one agent keeps the token hand-off (S6) consistent on both sides | `src/routes/auth.js:96-190` (new), `web/src/pages/ForgotPassword.tsx` (new), `web/src/pages/ResetPassword.tsx` (new), `web/src/api/auth.ts`, `web/src/App.tsx:20-48` | orch-dev-senior (opus/high), id a3de429a5d | 4 | 6 | both flows work against the stub mailer; S1–S6 implemented | `npm test`, `cd web && npm run build` |
| 6 | [~] | API docs and e-mail copy (subject, text, HTML) | `docs/api/auth.md` (new), `src/templates/email/reset-password.txt` (new), `src/templates/email/reset-password.html` (new) | orch-tech-writer (sonnet/medium), id b81f6c0e47 | 2 | 5 | docs match the contract; claims are checked against code in step 8 | step 8 |
| 7 | [ ] | Integration and e2e tests: request → stub mail → confirm; expired and reused token (concurrent), unknown address, rate limit, sessions revoked | `test/auth.reset.test.js` (new), `test/e2e/reset.spec.ts` (new) | orch-test-engineer (sonnet/medium) | 5 | — | every acceptance criterion has a test; each fails on a deliberately broken build | `npm test`, `npm run test:e2e` |
| 8 | [ ] | Final verification on the merged tree | whole diff | orch-build-verifier (haiku/low) ∥ orch-reviewer (opus/high) ∥ orch-security (best/high) ∥ orch-accessibility (sonnet/medium) ∥ orch-qa (sonnet/medium) | 5, 6, 7 | — | all ACCEPT; docs claims verified; rework loops closed | commands from the project map |
| 9 | [ ] | Production gate: snapshot → plan with backup and rollback → the user's yes → apply migration, deploy, post-checks | `deploy/`, runbook | orch-devops (opus/medium); `OWNER_APPROVED: yes` only after the yes | 8 | — | health OK, migration applied, one reset mail delivered to a test mailbox | health endpoint, row counts |

## Production gate
Nothing is migrated or deployed without the user's explicit yes (step 9).
- Actions after the yes: back up the database (timestamped, UTC) → apply `20260504_password_reset_tokens.sql` (new table only, no locks on existing tables) → deploy the new build → smoke checks: health endpoint and one reset mail to a test mailbox owned by the user.
- Rollback: `npm run migrate:down` (drops the new table) and redeploy the previous build. Sessions revoked by resets cannot be restored; those users sign in again.
- Approved by / when: — (pending)

## Risks
- Account enumeration: the request endpoint must answer identically for known and unknown addresses (S3); covered by a test in step 7.
- Token leakage through logs or the Referer header: hash at rest (S1), token in the URL fragment (S6), nothing logged.
- Session revocation (S5) touches the shared `sessions` table: verify it only affects the resetting user.
- Mail deliverability and provider limits cannot be tested with the stub; the first real mail is a post-deploy check.
- Budget: the estimate was ≈ 20%, and 74% of the 25% budget was spent with 4 of 9 steps done. The budget hook warns at 80%; then ask the user to extend the budget or drop optional reviews.

## Checkpoint
- Done: 1 recon (3 scouts + baseline) · 2 design review (S1–S6 folded into the briefs) · 3 backend core (dev-senior f6b3e1a924) · 4 verification (reviewers a0bfb4ae2d and 4a9d0c7e5b: ACCEPT after one rework round; build-verifier PASS)
- In flight: a3de429a5d (orch-dev-senior) — endpoints and web pages, started 18:20 · b81f6c0e47 (orch-tech-writer) — API docs and e-mail copy, started 18:42
- Next: step 7 (tests) when a3de429a5d reports; then step 8; step 9 only after the user's yes
- Open decisions / waiting for the user: none. Nothing is deployed without a yes.
- Key paths: `.claude/orchestrator/project-map.md` · `src/services/resetTokens.js` · `db/migrations/20260504_password_reset_tokens.sql`

## Result
<!-- Fill at the end: done / not done and why / verified how (commands → results) / owner actions /
     tokens: `python3 <skill>/scripts/costs.py --plan <this file>` -->
