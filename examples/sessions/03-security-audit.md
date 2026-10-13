# Session 3: a security audit (Fable is off)

The security-audit recipe from the [playbooks](../../skills/orchestrator/references/playbooks.md), run on a generic Node/Express API that the user owns. Two things are on show: the per-model limit (`fable: off` moves the Fable seats to Opus with effort max) and the refute panel for critical findings. Names, ids and numbers are illustrative; hook and report texts have the real formats.

## The request

```text
/orchestrator:orchestrator Audit the authentication and file-upload code of this API. We own it; production is read-only for you (config names and logs only). Confirmed findings only: file:line, scenario, fix.
```

## 1. The limits gate: Fable is off

Before the first step the UserPromptSubmit hook speaks, because a model status changed since the last prompt:

```text
[orchestrator limits] mode=normal session=18% week=58% context=3% models=fable:off,haiku:ok,opus:ok,sonnet:ok :: FABLE OFF: route every fable role to model=opus with effort=max (…)
```

`python3 scripts/limits.py` shows why: the session is fine, but Fable's weekly usage reached its threshold.

```text
model fable   off      week 25504930 / 30005800 (85%)
```

So every role whose default is `best` (security, protocol-reviewer, architect) is launched as `model: "opus", effort: "max"`. The work and the report formats stay the same; each of those agents costs more, so the orchestrator plans fewer and better-briefed ones. Size **M** (one API, two areas); Budget 15 % from the playbook hint.

```text
Plan .claude/plans/2026-05-12-security-audit.md   security-audit · M · Budget: 15% of the 5-hour limit
1 attack-surface maps          3 scouts (haiku/low) ∥ devops, read-only snapshot of config names and proxy rules
2 four lenses in parallel      security, protocol-reviewer (opus/max) ∥ privacy-compliance, dependency-auditor (sonnet)
3 dedupe and rank              orchestrator
4 refute panel for criticals   3 independent reviewers, different lenses; one reviewer for the highs
5 report; fixes are separate steps after your decision
```

## 2. Step 1: maps (cheap, parallel)

One message, four agents. The scouts map (a) auth, sessions, JWT, password handling, (b) uploads, storage, serving, (c) config, middleware, deployment files, dependency manifests. `orch-devops` (opus/medium, read-only) lists environment variable names (never values), the reverse-proxy rules, the service user and directory permissions. Result: 14 routes, 5 of them unauthenticated, uploads served by the app from local disk, JWT signed with an environment secret, nginx in front.

## 3. Step 2: four lenses in parallel

Two heavy agents and two Sonnet agents, within the normal-mode limit of four heavy. The Fable seats are overridden at the call:

```text
Agent(subagent_type: "orch-security",           model: "opus", effort: "max", prompt: <auth, sessions, uploads, limits>)
Agent(subagent_type: "orch-protocol-reviewer",  model: "opus", effort: "max", prompt: <JWT, password hashing, signed URLs>)
Agent(subagent_type: "orch-privacy-compliance", prompt: <PII in logs, upload metadata>)      # sonnet/high
Agent(subagent_type: "orch-dependency-auditor", prompt: <lockfile, npm audit, reachability>) # sonnet/medium
```

Each returns severity, `file:line`, a scenario, a fix and a "not verified" list:

- security: **C1 critical** `src/routes/files.js:31-44` path traversal in `GET /files/:name`; **H1** `files.js:22` no owner check on file metadata; M1 no rate limit on login.
- protocol-reviewer: **C2 critical (claimed)** `src/config.js:9` `JWT_SECRET || 'dev-secret'`, so tokens could be forged; M2 bcrypt cost 8 (`auth.js:44`).
- privacy-compliance: **H2** `auth.js:27` logs the whole request body on a validation error, so passwords reach the logs.
- dependency-auditor: **H3** `multer` 1.4.4, an advisory that is reachable through `POST /upload`; a dev-only `minimist` advisory is not reachable.

## 4. Step 3: dedupe and rank

The orchestrator merges the two reports about file serving, drops the unreachable advisory and ranks: two candidate criticals (C1, C2), three highs (H1 to H3). Only criticals get the panel; the highs get one reviewer. All of it runs at once: three panel members plus one reviewer is four heavy agents, still within the limit.

## 5. Step 4: the refute panel

Three independent agents, each told to **try to refute** both critical claims, each with a different lens, none shown the others' reasoning:

| Lens (agent) | C1 path traversal | C2 default secret |
|---|---|---|
| code path (`orch-reviewer`, opus/high) | not refuted: route registered, no normalisation after decoding | **refuted**: `src/server.js:12` aborts startup in production when the secret is unset |
| local reproduction (a fresh `orch-security`, opus/max) | not refuted: `GET /files/..%2f..%2fcanary.txt` returned a canary file placed outside the uploads folder | not refuted, but only with `NODE_ENV=development` and no secret |
| deployed config (`orch-devops`, opus/medium, read-only) | not refuted: the proxy forwards `%2f` unchanged; the service user can read the app directory, `.env` included | **refuted**: `JWT_SECRET` is present in the service environment (name only, value not read) |
| result | **confirmed, critical (3 of 3)** | **refuted as critical (1 of 3)**, re-rated Low: remove the fallback anyway |

The rule is "accept at two or more not-refuted". The panel did its job twice: it confirmed a real hole with a reproduction, and it killed an overclaim: the reader who raised it had missed the startup guard. The single reviewer for the highs re-derived H1 and H2 from the code and H3's reachability; DoS testing is out of scope for an audit, so H3 is "reachable, not exploited".

## 6. Finish

No code was changed and nothing on the server was modified (it was only read). The plan gets a Result; the budget line comes from `costs.py --plan`:

```text
budget (2026-05-12-security-audit.md, all sessions since 2026-05-12 10:20): 15% of the 5-hour limit → spent 11.6% = 77% → OK
```

Report to the user:

> **Auth and file upload: 1 critical and 3 high findings confirmed; 1 claimed critical refuted.**
> - **C1 critical**, `src/routes/files.js:31-44`: `GET /files/..%2f..%2f.env` returns any file the service user can read, including `.env` with the JWT secret. Reproduced locally with a canary file; the proxy does not block it. Fix: resolve the path and require it to stay inside `UPLOAD_DIR`.
> - **H1**, `files.js:22`: any logged-in user can read another user's file metadata by id. Fix: compare `file.ownerId` with `req.user.id`.
> - **H2**, `auth.js:27`: a failed validation logs the whole body, so passwords reach the logs. Fix: log field names only.
> - **H3**, `package.json:14` (`multer` 1.4.4): reachable advisory (memory exhaustion), not exploited here. Fix: upgrade, set `limits.fileSize` and `limits.files`.
> - **Refuted:** `JWT_SECRET || 'dev-secret'` (`src/config.js:9`) is not exploitable in production (startup guard, secret set); it is Low, remove the fallback anyway.
> - **Not verified:** DoS behaviour, rate limits under load, everything outside auth and uploads (CORS and sessions were not in the brief).
> - **Next, your call:** fix C1 and H1 to H3 as four bugfix steps, about 6 to 8 % of the limit, each with a second security look at the fix. Any production config change needs your explicit "yes".
> - **Cost:** 11.6 % of the 5-hour limit (budget 15 %). Security and protocol-review ran on Opus with maximum effort because Fable was off.

## What to notice

- Fable off changed the model, not the method: same roles, same formats, `effort: "max"` where Fable would have run.
- A critical finding is not believed until three different lenses fail to refute it; a claim that two lenses refute is downgraded, with the reason written down.
- Every finding carries a scenario and `file:line`; what was not checked is listed, not implied.
- Production was read, never changed.
