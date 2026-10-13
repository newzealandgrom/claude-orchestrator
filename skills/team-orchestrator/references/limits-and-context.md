# Limits and context — policy and mechanics

## Where the numbers come from (best first)

1. **Official status-line data** (`scripts/statusline.py` → `~/.claude/team-orchestrator/statusline.json`).
   Claude Code passes `rate_limits.five_hour` / `seven_day` (`used_percentage`, `resets_at`) to the status line
   for Pro/Max subscribers, and `context_window.used_percentage` to everyone. Used when younger than 10 min.
2. **Local transcripts** (`~/.claude/projects/**/*.jsonl`, incl. `*/subagents/*.jsonl`): every response's
   `usage` and `model`. Converted to *usage units* = model weight × (input + 5·output + 0.1·cache read +
   1.25/2·cache write). Grouped into 5-hour blocks and a rolling 7-day window, per model family.
3. **Real limit events** recorded by Claude Code (`error: "rate_limit"`, text like
   `You've hit your session limit · resets 3:50am (Europe/Berlin)`, `You've hit your Opus limit · …`,
   warnings `You've used 85% of your session limit`). They calibrate the caps: the units consumed up to a
   limit hit = the cap. Before the first hit the cap is the largest past block (`cap_source: history-max`,
   low confidence → thresholds act one level lower: ≥ 80 % → `economy`, ≥ 95 % → `critical`; a real limit error
   always means `exhausted`).
4. **Config** `~/.claude/team-orchestrator/limits.json` (see `examples/limits.example.json`) overrides caps,
   weights, thresholds and the context window.

Run: `python3 scripts/limits.py` (human), `--json` (machine), `--hook <Event>` (hooks; silent unless the state
degraded or changed; cached 60–120 s).

## Levels and what the orchestrator does

| Level | Trigger | Behaviour |
|---|---|---|
| normal | < 60 % of the tightest window | ≤ 4 heavy (Opus/Fable) agents in parallel; full verification ladder. |
| economy | ≥ 60 % | ≤ 2 heavy agents; Haiku for search/builds, Sonnet for analysis and docs; reviews only for risky diffs; no refute panels; batch questions to agents. |
| critical | ≥ 80 % | No new heavy agents. Finish in-flight work; checkpoint; report done/left and the reset time to the user; only cheap must-do checks. |
| exhausted | ≥ 95 % or an active limit error | Launch nothing. Checkpoint. After the reset, resume failed/finished agents with `SendMessage` (their transcripts persist) — do not re-brief. |

## Per-model routing

| Status | Trigger | Routing |
|---|---|---|
| fable `off` | Fable-specific limit error, Fable weekly ≥ 85 % of its cap, or session `critical`/`exhausted` | Every Fable/`best` role → `model: "opus", effort: "max"` (Agent tool), `--model opus --effort max` (spawn.sh). |
| fable `economy` | ≥ 60 % | Fable only as the judge for critical/protocol decisions. |
| opus `off` | "You've hit your Opus limit" | Senior roles → Sonnet, effort high (or Fable if available); sequential reviews. |
| sonnet `off` | "Sonnet limit" | Analysis/docs → Haiku high or Opus medium, whichever is available. |

Per-call `effort` needs Claude Code ≥ 2.1.292. `model: best` in agent files means "Fable if the account has it,
otherwise Opus".

## Failure handling (reactive — always on)

An agent result or notification containing `rate_limit`, `429`, `You've hit your … limit`:
1. Classify: model-specific (name in the text) vs session/weekly.
2. Model-specific → re-route that family (table above) and re-launch the step **by resuming** the failed agent
   with `SendMessage(to: <id>, …)` plus the override, or a new agent with `model`/`effort` overrides if the
   resume path is unavailable.
3. Session/weekly → `exhausted`: stop, checkpoint, tell the user the reset time; after reset resume each failed
   agent with "Limit reset — continue from where you stopped and return the result in the agreed format."

## Context of the orchestrator

- The model cannot run `/compact` or `/clear` — only the user can. So: keep the context lean, checkpoint early,
  and ask for `/compact` at the right moment.
- Lean: delegate all reading to subagents; ask for compact, structured reports (`file:line — fact`); never cat
  big files or full diffs; prefer resuming agents over re-briefing; spawn clean processes (`spawn.sh`) for long work.
- `context ≥ 50 %` → update the plan's `## Checkpoint`: done, in flight (agent ids + what they do), next step,
  open decisions, key paths. `≥ 75 %` → checkpoint, then ask the user: `/compact keep: plan <path>, running agent
  ids, next step`. After compaction (and on `resume`/`clear`) the `SessionStart` hook prints the active plan's
  checkpoint (`scripts/checkpoint.py`) so you continue from facts, not from a lossy summary.
- Optional tuning by the user: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (lower auto-compact threshold),
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`.

## Hooks shipped with the plugin

| Event | Command | Effect |
|---|---|---|
| `SessionStart` (`compact|resume|clear`) | `checkpoint.py --hook` | Re-injects the active plan checkpoint + limits line. |
| `PostToolUse` (`Agent`) | `limits.py --hook PostToolUse` | After each agent launch/finish: directive via `additionalContext` if the state degraded/changed. |
| `UserPromptSubmit` | `limits.py --hook UserPromptSubmit --cache-sec 120` | Same, once per user prompt. |

The status line cannot be shipped by a plugin: enable it once with `install.sh --statusline` or by adding
`"statusLine": {"type": "command", "command": "python3 <abs path>/scripts/statusline.py"}` to settings.
