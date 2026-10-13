# Production and irreversible actions

Covers: deploys, restarts, config/env changes, firewall, package upgrades, reboots, secret rotation, data deletion,
`git push`, publishing (repos, packages, artifacts), sending messages/emails, anything outward-facing.

## Rule
Nothing of the above happens without the user's explicit "yes" for **that step** in this conversation — unless the
user's request itself explicitly orders exactly that action (e.g. "fix it on production", "push it to my GitHub").
An approval does not extend to new, riskier steps discovered later (e.g. a second restart, a data migration):
ask, or make the step strictly reversible and report it.

## Order
1. `orch-devops` read-only snapshot (versions/hashes vs local, health, config names — never secret values,
   disk/RAM, active sessions/users).
2. Plan: exact commands, backups (timestamped in the server's UTC), rollback command per step, health checks,
   expected impact (e.g. "restart logs out N sessions").
3. User's yes (or the explicit order in the request).
4. `orch-devops` brief with `OWNER_APPROVED: yes` and the exact list of allowed actions; everything else forbidden.
5. Post-change checks (hashes equal local, health, logs without errors); a short incident-style report.

## Habits that prevented incidents
- Back up only what you change (no nested backups of backup folders).
- Do not use a deploy script blindly — read it first (it may rebuild or restart).
- Servers may cache files in memory (e.g. `index.html`): swapping static files can require a restart.
- Restart when active sessions are 0, or tell the user how many will be affected.
- Shared hosts: never touch other tenants' services; validate shared configs (`nginx -t`) before reload.
- Publishing: scan what will be published for secrets, personal data and internal hostnames first.
