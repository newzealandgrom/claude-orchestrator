# Session 1: a bugfix (the cookie survives logout)

One run of the [bugfix playbook](../../skills/orchestrator/references/playbooks.md), narrated step by step. A Node/Express app; names, ids and numbers are illustrative, the commands and report formats are real. Agents are written in the short form `orch-<role>`; with the plugin they are `orchestrator:orch-<role>`.

## The request

```text
/orchestrator:orchestrator After logout the session cookie stays in the browser, so the Back button shows the logged-in page. Node/Express app. Find the cause, fix it, add a regression test.
```

## 1. Limits gate and size

- `python3 scripts/limits.py` → `mode: NORMAL`, context 4 %. Nothing is injected by the hooks: they stay silent while everything is fine.
- Size **M**: the cause is unknown, two source files plus a test, no security protocol or production involved. Not S (needs a regression test and a review), not L (no architect needed).
- The project map `.claude/orchestrator/project-map.md` already exists (commands: `npm test`, `npm run lint`).

The plan, shown to the user in six lines and then executed without waiting (nothing irreversible):

```text
Plan .claude/plans/2026-04-21-logout-cookie.md   playbook: bugfix · size M · Budget: 6%
1. scout (haiku/low)             map the logout path and the cookie setup
2. test-engineer (sonnet/medium) failing regression test first
3. dev-middle (sonnet/medium)    minimal fix, two files
4. build-verifier (haiku/low) ∥ reviewer (opus/high)   suite, lint, adversarial review
Production: not touched. Estimate: about 3 % of the 5-hour limit.
```

## 2. Step 1: scout (haiku/low)

The scout is cheap and read-only, so it does all the searching; the expensive agents never search.

- → `orch-scout`: where is the `sid` cookie set and cleared; which tests touch logout; how are tests run?
- ← `src/middleware/session.js:12-35` cookie options (`domain` from `COOKIE_DOMAIN`, `sameSite`, `maxAge`); `src/routes/auth.js:52-71` `POST /logout` calls `res.clearCookie('sid')` with no options; `test/auth.test.js` covers login only.

The orchestrator reads those two ranges (about 40 lines) to accept the map and states the hypothesis: the cookie is set with `Domain=.example.com`, the clearing header has no Domain, so the browser keeps the original.

## 3. Step 2: test-engineer (sonnet/medium)

- → `orch-test-engineer`: write the regression test first; logout must clear `sid` with the same Domain and Path and an expiry in the past; do not touch production code.
- ← `test/auth.logout.test.js:1-48`, three tests. `npm test -- test/auth.logout.test.js` → 2 passed, 1 failed: `expected Set-Cookie to contain "Domain=.example.com"`.
- Gate passed: the test fails for the stated reason, which also confirms the hypothesis.

## 4. Step 3: dev-middle (sonnet/medium)

The brief is the example in [brief-bugfix.md](../brief-bugfix.md): ranges, the two files the agent may edit, a negative scenario, three commands. Sonnet is enough: the change is small and fully specified.

- ← `src/middleware/session.js:12-38` cookie options moved into an exported `COOKIE_OPTIONS` (without `maxAge`); `src/routes/auth.js:55` `res.clearCookie('sid', COOKIE_OPTIONS)`.
- ← `npm test -- test/auth.logout.test.js` 3 passed · `npm test` 61 passed · `npm run lint` 0 problems.

## 5. Step 4: verification in parallel

Two independent checks in one message, so they run concurrently.

- `orch-build-verifier` (haiku/low): `npm test` PASS (61 passed), `npm run lint` PASS. Nothing else; it does not analyse.
- `orch-reviewer` (opus/high), told to try to refute "done", including every other place that sets or clears the session cookie:

```text
Verdict: REWORK
1. HIGH   src/routes/api.js:84-96   DELETE /api/session ("log out everywhere" in the SPA) has the same bare
          res.clearCookie('sid'). Scenario: user clicks it, cookie stays, Back shows the account page. Fix: COOKIE_OPTIONS.
2. LOW    src/routes/auth.js:54     if session.destroy() fails, next(err) runs before clearCookie: 500 and the cookie stays.
Not refuted: Domain, Path, SameSite match; maxAge is excluded; 204 kept; other cookies untouched.
```

## 6. The fix loop

- Finding 1 must be fixed. The orchestrator first resumes the same test-engineer with `SendMessage`: add the same assertion for `DELETE /api/session`; it must fail. It does.
- Then `SendMessage` to the same dev-middle (its context is intact, no new brief): the findings, plus permission to edit `src/routes/api.js`. Result: `src/routes/api.js:88` uses `COOKIE_OPTIONS`; `npm test` 62 passed; `npm run lint` 0 problems.
- Finding 2 is a behaviour change on an error path, so it is not fixed silently: it goes into the report as a decision for the user.
- Round 2: `SendMessage` to the same reviewer, "check only the fixes". Verdict ACCEPT; the build-verifier is re-run: PASS.

## 7. Finish

The plan gets `Status: done` and a Result section; actual spend comes from `python3 scripts/costs.py --plan .claude/plans/2026-04-21-logout-cookie.md`:

```text
budget (2026-04-21-logout-cookie.md, all sessions since 2026-04-21 10:05): 6% of the 5-hour limit → spent 3.1% = 52% → OK
```

Report to the user:

> **Fixed: the session cookie now disappears on logout.**
> Cause: `res.clearCookie('sid')` was called without the options the cookie was set with (`Domain=.example.com`), so the browser treated it as a different cookie and kept the original.
> Changed: `src/middleware/session.js:12-38` (shared `COOKIE_OPTIONS`), `src/routes/auth.js:55` and `src/routes/api.js:88` (`clearCookie('sid', COOKIE_OPTIONS)`), new `test/auth.logout.test.js` (4 tests).
> Verified: `npm test` → 62 passed (was 58); `npm run lint` → 0 problems; the new tests fail on the old code; reviewer round 2: ACCEPT.
> Not verified: a real browser. Please check once: log in, log out, press Back, look at DevTools → Application → Cookies.
> Needs your decision: when `session.destroy()` fails (session store down), `/logout` answers 500 and keeps the cookie (`src/routes/auth.js:54`). A one-line change, left out because it alters error behaviour. Say "yes" and it is done.
> Cost: about 3 % of the 5-hour limit (budget 6 %).

## What to notice

- The orchestrator read about 40 lines of code in total; scouts, a test-engineer and a developer did the reading and writing.
- The test failed before the fix, so it proves something; the fix was accepted only after a reviewer tried to break it.
- The reviewer found what the scout was never asked about. That is the point of an adversarial lens; it is cheaper than a second bug report.
- Rework went back to the same agents with `SendMessage`; nobody was re-briefed from scratch, and round 2 re-checked only the fixes.
- The Budget line set from the playbook hint kept the run honest: 52 % used, no hook warning (the budget hook speaks at 80 %).
