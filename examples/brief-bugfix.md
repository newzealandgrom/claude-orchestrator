# Example brief: session cookie survives logout

A filled-in [`templates/brief.md`](../skills/orchestrator/templates/brief.md): step 3 of the bugfix walkthrough in [sessions/01-bugfix.md](sessions/01-bugfix.md) (a Node/Express app; all names and numbers are illustrative). The agent receives only the text in the block below, so the block must carry everything it needs.

~~~text
ROLE: orch-dev-middle · PLAN: .claude/plans/2026-04-21-logout-cookie.md, step 3
GOAL: After `POST /logout` the browser drops the `sid` cookie: the response clears it with the same Domain, Path and SameSite it was set with.

CONTEXT (ready-made, do not search again):
- src/middleware/session.js:12-35 — session setup; the cookie options (`domain: process.env.COOKIE_DOMAIN`, `path`, `httpOnly`, `secure`, `sameSite`, `maxAge`) are an inline literal → read with `sed -n 12,35p src/middleware/session.js`
- src/routes/auth.js:52-71 — `POST /logout`: `req.session.destroy()`, then `res.clearCookie('sid')` with no options → read with `sed -n 52,71p src/routes/auth.js`
- test/auth.logout.test.js:1-48 — regression test written in step 2; it fails today on the Domain assertion (expected `Domain=.example.com`, got none). Do not edit it.
- Root cause (step 1): a cookie set with `Domain=.example.com` is removed only by a Set-Cookie with the same Domain and Path; the bare `clearCookie('sid')` targets a different, host-only cookie.
- Express rule: `res.clearCookie(name, options)` needs the same options as `res.cookie`, except `expires` and `maxAge`.

DO:
1. In src/middleware/session.js move the cookie options (everything except `maxAge`) into an exported constant `COOKIE_OPTIONS`; build the session config from it plus `maxAge`.
2. In src/routes/auth.js:55 call `res.clearCookie('sid', COOKIE_OPTIONS)`.
3. Leave `req.session.destroy` and the 204 response as they are.

CONSTRAINTS:
- You may edit only: src/middleware/session.js, src/routes/auth.js. Everything else: report, do not touch.
- Do not change: cookie name, lifetime, `sameSite` and `secure` values, the session store, any other route.
- Do not pass `maxAge` or `expires` to `clearCookie`.

DONE WHEN:
- `npm test -- test/auth.logout.test.js` passes: the logout response carries `sid=; Domain=.example.com; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax` (plus `Secure` in production).
- Negative: `POST /logout` without a session cookie still answers 204 and does not throw; a cookie with another name is left alone.

VERIFY (run yourself, attach output):
- `npm test -- test/auth.logout.test.js`
- `npm test`
- `npm run lint`

PRODUCTION: do not touch.
REPORT FORMAT: data for the orchestrator — changes as `file:lines — what`, command outputs, deviations with reasons, what is not done. No prose.
~~~

## Why it looks like this

- **Ranges, not files.** Every `CONTEXT` line gives `file:A-B` and the `sed -n` command, so a Sonnet-class agent never opens a whole file or searches for what the scout already found.
- **One writer per file.** `You may edit only` is explicit; the regression test belongs to the test-engineer from step 2 and is read-only here.
- **A negative scenario.** `DONE WHEN` names something that must fail safely, not only the happy path.
- **Proof, not promises.** The agent runs the commands and attaches the output; the orchestrator never accepts a step on the developer's word (see [verification.md](../skills/orchestrator/references/verification.md)).
- **Production is always spelled out**, here as `do not touch`; a step that may change a server uses `OWNER_APPROVED: yes` and the exact action list instead (see [production-gate.md](../skills/orchestrator/references/production-gate.md)).
