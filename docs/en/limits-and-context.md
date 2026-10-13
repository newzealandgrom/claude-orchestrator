# Limits and context

[Русская версия](../ru/limits-and-context.md) · [README](../../README.md) · [Usage guide](usage-guide.md)

How the orchestrator decides how much work to launch, on which model, and when to save its state. Source of truth:
`skills/team-orchestrator/scripts/limits.py`, `statusline.py`, `checkpoint.py` and
`skills/team-orchestrator/references/limits-and-context.md`.

Everything is local and read-only. The scripts have no network code; they read usage counters, model ids,
timestamps and the text of limit messages from your Claude Code transcripts and write small state files to
`~/.claude/team-orchestrator/`. **All numbers except the official status-line ones are estimates.**

## Running it

```bash
python3 skills/team-orchestrator/scripts/limits.py            # human-readable
python3 skills/team-orchestrator/scripts/limits.py --json     # machine-readable
python3 skills/team-orchestrator/scripts/limits.py --config ~/my-limits.json
python3 skills/team-orchestrator/scripts/limits.py --session-file <transcript.jsonl> --context-window 1000000
```

Other flags: `--hook [EVENT]` (hook mode, see below), `--always` and `--cache-sec N` (hook mode only), `--now <ISO time>`
(testing). With a manual install the scripts are also in `~/.claude/team-orchestrator/`.

Human output has this shape (values illustrative):

```
mode: ECONOMY
session 5h: 18400000 / 27000000 units (68%, cap: observed-limit), block 2026-10-13T09:10:00+00:00 -> 2026-10-13T14:10:00+00:00
week 7d:    61000000 / ? units (n/a)
model fable   ok       week 9000000 / ? (n/a)
model opus    ok       week 30000000 / ? (n/a)
context: 410000 / 1000000 tokens (41%) -> ok  [<session>.jsonl]
actions:
  - ECONOMY: max 2 parallel heavy agents; no refute panels; prefer haiku for search/build, sonnet for analysis; reviews only for risky changes.
```

## Data sources (best first)

1. **Official status-line data.** `statusline.py` saves what Claude Code passes to the status line into
   `~/.claude/team-orchestrator/statusline.json`: `rate_limits.five_hour` / `seven_day` (`used_percentage`,
   `resets_at`) for Pro/Max subscribers, and `context_window.used_percentage` for everyone. `limits.py` uses the file
   only if it is younger than 10 minutes. When present, it replaces the estimated 5-hour and 7-day percentages and the
   block end time (`cap_source: statusline`).
2. **Local transcripts.** `~/.claude/projects/*/*.jsonl` and `~/.claude/projects/*/*/subagents/*.jsonl`, files
   modified within the last 8 days; every project is scanned, so usage is machine-wide. Each assistant response's
   `usage` and `model` are counted once (de-duplicated by message id).
3. **Real limit events recorded in the transcripts.** Error messages such as
   `You've hit your session limit · resets 3:50am (Europe/Berlin)` or `You've hit your Opus limit · …`, and
   warnings such as `You've used 85% of your session limit`. They calibrate the caps.
4. **Config** `~/.claude/team-orchestrator/limits.json` overrides caps, weights, thresholds and the context window.

Not seen by the script: usage from other devices, claude.ai chats, or another `CLAUDE_CONFIG_DIR`.

## Usage units

```
units = model_weight × ( input + 5·output + 0.1·cache_read + 1.25·cache_write_5m + 2·cache_write_1h )
```

Cache writes without a 5m/1h breakdown are counted as 5m. Default weights (relative cost per family, `model_weights`):
fable 2.0, opus 1.0, sonnet 0.6, haiku 0.2, other 1.0. The family is found by substring in the model id (`fable`,
`opus`, `sonnet`, `haiku`).

## Windows and caps

- **Session blocks.** Usage is grouped into 5-hour blocks starting at the first request after the previous block ended.
  When a limit message gives a reset time, the block is pinned to `[reset − 5 h, reset)`.
- **Week.** Rolling 7 days.
- **Session cap calibration.** For each real session-limit event, the units consumed in the 5 hours before the hit
  are a cap sample. For each `used N%` warning (N above 20), `units / N` is a sample. The largest sample wins
  (`cap_source: observed-limit`).
- **Before any hit.** The cap is the largest completed past block (`cap_source: history-max`) — a low-confidence guess.
  With no completed block there is no cap and no percentage.
- **Weekly and per-model caps** are calibrated the same way from weekly / `Opus limit` / `Fable limit` events and
  warnings, over the preceding 7 days.
- **Config wins.** `session_cap_units`, `weekly_cap_units` and `model_weekly_cap_units` take priority over
  calibration (`cap_source: config`).
- **Reset time parsing** understands forms like `resets 3:50am (Europe/Berlin)`, a weekday, or a month and day;
  an unknown time zone is treated as UTC.

## Levels

The level (`mode`) is derived from the larger of the session and weekly percentages.

| Level | Trigger | Orchestrator behaviour |
|---|---|---|
| normal | below 60 % | up to 4 heavy (Opus/Fable) agents in parallel; full verification ladder |
| economy | 60 % and above | up to 2 heavy agents; Haiku for search/builds, Sonnet for analysis and docs; reviews only for risky diffs; no refute panels; batch questions to agents |
| critical | 80 % and above | no new heavy agents; finish in-flight work; checkpoint; report done/left and the reset time; only cheap must-do checks |
| exhausted | 95 % and above, or an active limit event | launch nothing; checkpoint; after the reset resume agents with `SendMessage` |

Two rules from the code:

- An **active** session, weekly or unknown limit event (reset time still ahead; if the text has no reset time, 5 h for
  session events and 1 h otherwise) forces `exhausted`.
- While the cap is only `history-max`, thresholds are downgraded one step: 95 % and above gives `critical` (not
  `exhausted`), 80 % and above gives `economy`. 60–80 % is `economy` in any case.

## Per-model routing

Per family (`fable`, `opus`, plus any family seen in the last 8 days), weekly usage against its cap:

| Status | Trigger | Routing |
|---|---|---|
| `off` | an active limit event for that model; weekly share at or above `model_thresholds.off` (0.85); session `exhausted` (all families); or, for `fable` only, session `critical` | see below |
| `economy` | weekly share at or above `model_thresholds.economy` (0.60), or session `critical` | see below |
| `ok` | otherwise | normal |

Routing the orchestrator applies:

| Condition | Action |
|---|---|
| Fable `off` | every Fable/`best` role runs on Opus with effort max: `Agent(subagent_type, model: "opus", effort: "max")` or `spawn.sh … --model opus --effort max` |
| Fable `economy` | Fable only as judge of critical/protocol decisions; other Fable roles -> Opus max |
| Opus `off` | senior roles -> Sonnet with effort high (or Fable if available); reviews sequential |
| Sonnet `off` | analysis and docs -> Haiku high or Opus medium (from the reference policy; `limits.py` does not currently print a directive for it) |

Fable is switched off first when the session budget gets tight because it is the most expensive. Per-call `effort`
requires Claude Code 2.1.292 or newer. `model: best` in agent files means Fable if the account has it, otherwise
Opus. Without Fable access, the Fable rows never apply in practice.

## Failure handling (always on)

If an agent result or notification contains `rate_limit`, `429` or `You've hit your … limit`, the orchestrator:

1. Classifies it: model-specific (the model name is in the text) or session/weekly.
2. Model-specific: re-routes that family (table above) and re-launches the step by resuming the failed agent with
   `SendMessage(to: <id>, …)` plus the model/effort override; if resuming is impossible, a new agent with overrides.
3. Session/weekly: treats it as `exhausted` — stops, writes the checkpoint, tells you the reset time. After the reset
   each failed agent is resumed with "Limit reset — continue from where you stopped and return the result in the
   agreed format."

It also re-runs the gate after every agent completion in long runs.

## Context of the orchestrator

The model cannot run `/compact` or `/clear`; only you can. So the orchestrator keeps its context lean (delegates all
reading, asks for `file:line — fact` reports, resumes agents instead of re-briefing) and acts on the fill level:

| Fill | Status | Action |
|---|---|---|
| below 50 % | ok | — |
| 50 % and above | `checkpoint` | rewrite the plan's `## Checkpoint` (done, running agent ids, next step, open decisions, key paths); stop reading files itself |
| 75 % and above | `compact` | checkpoint, then ask you: `/compact keep: plan <path>, running agent ids, next step` (or start a new session and resume from the plan) |

Fill comes from the status-line snapshot when it belongs to the same session, otherwise from the newest transcript of
the current directory's project (last non-sidechain assistant response: input + cache read + cache write + output
tokens). The window is `context_window` from config, else the value the status line reports, else 200k (1M if more
than 200k was ever observed or the model id contains `[1m]`).

After `/compact`, `/clear` or resume, the `SessionStart` hook runs `checkpoint.py --hook`: it picks the newest
`.claude/plans/*.md` whose header has `Status: in-progress`, and prints its first 12 lines, the `## Checkpoint` section
(up to 80 lines) and the current limits line. Claude Code adds that output to the new context. No in-progress plan:
the hook prints nothing.

Optional tuning (Claude Code settings, not this plugin): `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`,
`CLAUDE_CODE_AUTO_COMPACT_WINDOW`.

## Hooks

| Event | Command | Effect |
|---|---|---|
| `SessionStart` (`compact\|resume\|clear`) | `checkpoint.py --hook` | re-injects checkpoint + limits line |
| `PostToolUse` (`Agent`) | `limits.py --hook PostToolUse` | directive via `additionalContext` if the state degraded or changed |
| `UserPromptSubmit` | `limits.py --hook UserPromptSubmit --cache-sec 120` | same, once per prompt |

How `limits.py --hook` behaves: it keeps the last state (mode, per-model statuses, context status) in
`~/.claude/team-orchestrator/last-state.json` and speaks only when it changed. The first call stays silent if
everything is fine. Reports are cached in `last-report.json` for `--cache-sec` seconds (default 60; 120 for
`UserPromptSubmit`), so the transcripts are not rescanned on every call. Any exception is printed to stderr and the
hook exits 0, so it cannot break a session. The message looks like
`[team-orchestrator limits] mode=economy session=68% week=n/a context=41% models=fable:ok,opus:ok :: ECONOMY: …`.
`--always` forces output even if unchanged.

Plugin installs get the hooks from `hooks/hooks.json`. For a manual install add `--hooks` to `install.sh`; it registers
the same three hooks pointing at `~/.claude/team-orchestrator/`.

## Status line

`statusline.py` prints one line and saves the snapshot described above:

```
Opus 5.5 · ctx 41% · 5h 63% ↻14:50 · 7d 22%
```

The `5h` and `7d` parts appear only if Claude Code supplies `rate_limits` (Pro/Max); `ctx` appears whenever the
context percentage is available; `↻` is the local reset time. A plugin cannot ship a status line, so enable it:

```bash
./install.sh --statusline-only        # plugin users; or add --statusline to a manual install
```

It copies the scripts to `~/.claude/team-orchestrator/` and sets `statusLine` in `~/.claude/settings.json` (backup
first). If you already had a status line, its command is stored in `ORCH_STATUSLINE_NEXT`; its output is appended after
`|` (5-second timeout). Manual alternative:

```json
"statusLine": { "type": "command", "command": "python3 /ABS/PATH/statusline.py" }
```

`./uninstall.sh` restores the previous status line.

## Configuration

File: `~/.claude/team-orchestrator/limits.json`, or `$ORCH_LIMITS_CONFIG`, or `--config`. The first existing one is
used; its keys are merged over the defaults (nested objects are merged key by key). Template:
`examples/limits.example.json`.

```json
{
  "session_cap_units": null,
  "weekly_cap_units": null,
  "model_weekly_cap_units": { "fable": null, "opus": null },
  "model_weights": { "fable": 2.0, "opus": 1.0, "sonnet": 0.6, "haiku": 0.2, "other": 1.0 },
  "thresholds": { "economy": 0.60, "critical": 0.80, "exhausted": 0.95 },
  "model_thresholds": { "economy": 0.60, "off": 0.85 },
  "context_window": null,
  "context_thresholds": { "checkpoint": 0.50, "compact": 0.75 }
}
```

Examples:

```json
{ "session_cap_units": 40000000 }
```
Pins the 5-hour cap. Use it after you have seen the real number in `limits.py` output once a limit message was
recorded, or if the estimate keeps being off.

```json
{ "thresholds": { "economy": 0.50, "critical": 0.70, "exhausted": 0.90 } }
```
A more cautious orchestrator.

```json
{ "context_window": 200000, "context_thresholds": { "checkpoint": 0.40, "compact": 0.65 } }
```
Forces a 200k window and earlier checkpoints.

```json
{ "model_weekly_cap_units": { "fable": 6000000 } }
```
Gives Fable a weekly cap so its share can reach `economy`/`off` before a real Fable limit error.

## Troubleshooting

**The mode is `economy` (or `critical`) but I have not hit any limit.** Before the first recorded limit event the cap
is the largest completed past block (`cap_source: history-max`). If the current block is larger than every earlier one, the percentage is
over 100 % by construction, and a small history makes the cap too low. Run `limits.py` and check `cap_source`. Fixes: set
`session_cap_units`; enable the status line (Pro/Max) so official percentages are used; or raise `thresholds`.

**`cap: history-max` and `n/a` percentages.** No completed block in the last 8 days yet; there is nothing to compare
with. The mode stays `normal` until data accumulates (context checks still work).

**Status line is blank.** Check the settings: `statusLine` must point at an existing `statusline.py` (`python3` in
`PATH`). Claude Code only runs a status line command after the workspace is trusted, so accept the trust dialog for
the folder first. Run `echo '{}' | python3 ~/.claude/team-orchestrator/statusline.py` — it should print a line.
This trust requirement comes from Claude Code, not from this package; see the Claude Code documentation.

**No `5h` / `7d` in the status line.** `rate_limits` is supplied only for Pro/Max subscribers. Otherwise the estimates from transcripts are used.

**`context` shows `unknown`.** No transcript was found for the current directory and the status-line snapshot is
older than 10 minutes or from another session. Enable the status line, or pass `--session-file`.

**Percentages disagree with `/usage`.** Expected: estimates cover only this machine's transcripts and use a fixed
price structure. Trust the official numbers; pin caps in config if you want estimates close to them.

**The hook never speaks.** By design it is silent while everything is `normal`/`ok` and nothing changed. Check
`~/.claude/team-orchestrator/last-state.json`, or run `limits.py --hook --always`.

**Hooks fire twice.** You installed the plugin and also ran `install.sh --hooks`. Remove one
(`./uninstall.sh` removes the manual entries).

**Python version.** Needs 3.9+ (`zoneinfo`); on older versions time zones in reset texts fall back to UTC.
