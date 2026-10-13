# Plan: <title>

**Date:** YYYY-MM-DD · **Status:** in-progress
**Started:** YYYY-MM-DD HH:MM · **Budget:** 25% <!-- of the 5-hour limit, or e.g. 4M tokens; costs.py warns at 80 % -->
**Playbook:** <bugfix | feature | refactor | migration | upgrade | security-audit | performance | incident | release | docs | tests | onboarding>
**Request (verbatim):** "<user request>"
**Size:** S|M|L · **Token estimate:** … · **Actual:** —
**Touches production / publishes:** yes|no (steps …)
**Limits at start:** `python3 <skill>/scripts/limits.py` → mode …, fable …, context …

## Goal and scope
What must be true at the end; what is explicitly out of scope.

## Recon (facts with sources)
- …

## Steps
| # | Status | What | Files | Agent (model/effort) | Depends on | Parallel with | Done when | Verify |
|---|---|---|---|---|---|---|---|---|
| 1 | [ ] | … | `path:A-B` | orch-scout (haiku/low) | — | 2 | map returned | — |
<!-- Status: [ ] to do · [~] in progress · [x] done — /orchestrator:status counts these -->

## Production gate
Exact actions, backups, rollback, who approved and when.

## Risks
- …

## Checkpoint
<!-- Keep current. Re-injected after /compact by the SessionStart hook. -->
- Done: …
- In flight: <agent id> — <what>, started <time>
- Next: …
- Open decisions / waiting for the user: …
- Key paths: …

## Result
<!-- Fill at the end: done / not done and why / verified how (commands → results) / owner actions /
     tokens: `python3 <skill>/scripts/costs.py --plan <this file>` -->
