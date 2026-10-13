# Changelog

## 2.0.0 — 2026-10-13 — "Claude Orchestrator"

**Breaking: new names.** The plugin is now `orchestrator` in the marketplace `claude-orchestrator`
(the product name is Claude Orchestrator, matching the repository). Migrate from 1.x:

```
/plugin uninstall team-orchestrator@team-orchestrator
/plugin marketplace remove team-orchestrator
/plugin install orchestrator --marketplace newzealandgrom/claude-orchestrator
```

Manual installs: `git pull && ./install.sh` — it removes the old `skills/team-orchestrator` folder and migrates
v1 status line / hooks entries in settings.json automatically (your own status line is kept). Data moved from `~/.claude/team-orchestrator/` to `~/.claude/claude-orchestrator/`
(the old status snapshot is still read as a fallback).

### Added
- **12 new roles (27 in total):** researcher, frontend, mobile, db-engineer, api-designer, test-engineer,
  performance, accessibility, privacy-compliance, dependency-auditor, incident-responder, release-manager.
- **Short commands** (plugin): `/orchestrator:status` (dashboard), `/orchestrator:limits`, `/orchestrator:costs`,
  `/orchestrator:resume`, `/orchestrator:setup` (status line in one step; `setup remove` removes it again). Manual installs:
  `/orchestrator status|limits|costs|resume`.
- **Costs per role:** `scripts/costs.py` — tokens, weighted units and ≈ % of the 5-hour/weekly limit per role
  and per agent, top consumers, JSON output.
- **Plan budgets:** `Budget: 25%` (of the 5-hour limit) or `Budget: 4M tokens` in the plan header; the new
  `PostToolUse(Agent)` budget hook warns once at 80 % and stops new agents at 100 %.
- **Self-calibration:** while official status-line numbers are fresh, `limits.py` learns the units per 1 % of each
  limit and the official window boundaries; a stale snapshot falls back to this scale (`cap: calibrated`) instead of
  the history guess.
- **Playbooks:** `references/playbooks.md` — bugfix, feature, refactor, migration, dependency upgrade, security audit,
  performance, incident, release, docs, test coverage, onboarding.
- `checkpoint.py --status` (plan progress from `[ ]`/`[~]`/`[x]` markers + checkpoint + limits + costs).
- `SessionStart(startup)` hook keeps the status line's stable copy of the scripts current after plugin updates.
- `examples/`: 30+ prompts (EN/RU), a filled plan and brief, three session walkthroughs, sample outputs.
- Bilingual one-page README with a language switcher, step-by-step install for first-timers, diagrams and graphics.

### Changed
- Plan template: `Started:`, `Budget:`, `Playbook:` and a status column in the steps table.
- `install.sh`/`uninstall.sh` share `scripts/patch_settings.py`; reinstall is idempotent; v1 entries are migrated.
- Hook messages are prefixed `[orchestrator limits]` / `[orchestrator budget]` / `[orchestrator]`.

## 1.0.0 — 2026-10-13
- First public release: `team-orchestrator` skill + 15 role subagents (`orch-*`), plugin + marketplace in one repo.
- Limits gate: `scripts/limits.py` (5-hour session, weekly, per-model; calibration from real limit errors and
  "used N%" warnings; official status-line numbers on Pro/Max), automatic Fable → Opus (effort max) re-routing.
- Context management: plan checkpoints, `/compact` guidance, `SessionStart` hook re-injects the active plan checkpoint.
- Hooks: `SessionStart` (compact|resume|clear), `PostToolUse` (Agent), `UserPromptSubmit`.
- `statusline.py` (model · context · 5h · 7d, chains an existing status line), `spawn.sh`/`collect.sh` for clean-context
  agent processes, `install.sh`/`uninstall.sh` for manual installs.
