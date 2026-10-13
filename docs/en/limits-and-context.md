# Limits and context

[Русская версия](../ru/limits-and-context.md) · [README](../../README.md) · [Usage guide](usage-guide.md)

How Claude Orchestrator decides how much work to launch and on which model, when to save its state, and what the work
costs. Source of truth: the scripts in `skills/orchestrator/scripts/` (`limits.py`, `costs.py`, `statusline.py`,
`checkpoint.py`), the plugin helper `scripts/sync_stable.py` and
[`skills/orchestrator/references/limits-and-context.md`](../../skills/orchestrator/references/limits-and-context.md).

Everything is local and read-only. The scripts have no network code; they read usage counters, model ids, timestamps
and the text of limit messages from your Claude Code transcripts and write small state files to
`~/.claude/claude-orchestrator/` (the base directory follows `CLAUDE_CONFIG_DIR`). **All numbers except the official
status-line ones are estimates.** Values in the examples below are illustrative.

```
 status line (Pro/Max) ──► statusline.json ──┐
 transcripts of all projects ────────────────┤
 limit errors, "used N%" warnings ───────────┼──► limits.py ──► mode · per-model status · context · actions
 limits.json (optional) ─────────────────────┘        │
                                                      └──► calibration.json ──► costs.py (≈ % of limits, % budgets)
```

## At a glance

| I want to … | Do this |
|---|---|
| See the current mode and why | `/orchestrator:limits` |
| See who spent what | `/orchestrator:costs` |
| Get exact official numbers instead of estimates (Pro/Max) | `/orchestrator:setup` once — it turns on the [status line](#status-line) |
| Cap what one task may spend | A `Budget:` line in the plan header — [Plan budgets](#plan-budgets) |
| Fix a wrong estimate of the 5-hour cap | `session_cap_units` in [`limits.json`](#configuration) |
| Survive `/compact`, `/clear`, a restart or a limit reset | Plan checkpoint + `/orchestrator:resume` — [Context](#context-of-the-orchestrator) |

## Running it

Inside Claude Code (plugin install): `/orchestrator:limits` explains the report in a few lines, `/orchestrator:costs`
shows the spend, `/orchestrator:status` adds plan progress. From a shell, in a clone of the repository (after the status
line is set up the scripts are also in `~/.claude/claude-orchestrator/`):

```bash
python3 skills/orchestrator/scripts/limits.py            # human-readable
python3 skills/orchestrator/scripts/limits.py --json     # machine-readable
python3 skills/orchestrator/scripts/limits.py --config ~/my-limits.json
python3 skills/orchestrator/scripts/limits.py --session-file <transcript.jsonl> --context-window 1000000
```

| Option | Meaning |
|---|---|
| `--json` | Machine-readable report: `mode`, `data_source`, `session`, `weekly`, `models`, `active_limits`, `context`, `actions`, `calibration`. |
| `--config FILE` | Use this limits config. |
| `--session-file PATH` | Transcript of the orchestrator's conversation (default: the newest one of the current directory's project). |
| `--context-window N` | Context window of the orchestrator's model, in tokens. |
| `--hook [EVENT]` | Hook mode (see [Hooks](#hooks)): print a short directive only when the state degraded or changed. `EVENT` is `PostToolUse`, `UserPromptSubmit` or `SessionStart` (JSON `additionalContext`); without a value the text is plain. |
| `--always` | With `--hook`: report even if nothing changed. |
| `--cache-sec N` | With `--hook`: reuse a report younger than N seconds (default 60). |
| `--now ISO` | Override the current time (for testing). |

The human output has this shape:

```
mode: ECONOMY
session 5h: 28961327 / 45970360 units (63%, cap: statusline), block 2026-05-04T09:50:00+00:00 -> 2026-05-04T14:50:00+00:00
week 7d:    118402220 / 249695560 units (47%)
model fable   ok       week 21304118 / ? (n/a)
model haiku   ok       week 559344 / ? (n/a)
model opus    ok       week 92131516 / ? (n/a)
model sonnet  ok       week 4407242 / ? (n/a)
context: 412880 / 1000000 tokens (41%) -> ok  [3f2a9c1e-….jsonl]
calibration 5h: 1% ≈ 459704 units (learned at 59%, 2026-05-04T12:31Z)
calibration 7d: 1% ≈ 2496956 units (learned at 47%, 2026-05-04T12:31Z)
source: statusline+transcripts
actions:
  - ECONOMY: max 2 parallel heavy agents; no refute panels; prefer haiku for search/build, sonnet for analysis; reviews only for risky changes.
```

Reading it, line by line:

- `mode` — the level ([Levels](#levels)).
- `session 5h` — units used in the current 5-hour window, the cap, the percentage, where the cap comes from (`cap:`,
  see [Windows and caps](#windows-and-caps)) and the window boundaries. With `cap: statusline` the percentage is the
  official one; the `units / cap` pair next to it is the local estimate.
- `week 7d` — the same for the rolling week.
- `model …` — per model family: status (`ok`, `economy`, `off`), weekly units and the cap. `?` and `n/a` mean that no
  cap is known for that family yet.
- `context` — tokens in the orchestrator's conversation, the window, the percentage and the status.
- `calibration …` — the scale learned from official numbers ([Self-calibration](#self-calibration)); printed only when
  there is one.
- `source` — `statusline+transcripts` (a fresh official snapshot), `calibrated+transcripts` (no fresh snapshot, the
  learned scale is used) or `transcripts` (estimates only).
- `ACTIVE LIMIT …` lines appear while a real limit event is still in force.
- `actions` — what the orchestrator will do about it.

## Where the numbers come from (best first)

1. **Official status-line data.** `statusline.py` saves what Claude Code passes to the status line into
   `~/.claude/claude-orchestrator/statusline.json`: `rate_limits.five_hour` / `seven_day` (`used_percentage`,
   `resets_at`) for Pro/Max subscribers, and `context_window.used_percentage` for everyone. `limits.py` uses the file
   only if it is younger than 10 minutes. When present, it replaces the estimated 5-hour and 7-day percentages and the
   block end time (`cap: statusline`).
2. **Local transcripts.** `~/.claude/projects/*/*.jsonl` and `~/.claude/projects/*/*/subagents/*.jsonl`, files
   modified within the last 8 days; every project is scanned, so usage is machine-wide. Each assistant response's
   `usage` and `model` are counted once (de-duplicated by message id). Subagent transcripts are included, so the work of
   every role is counted.
3. **Real limit events recorded in the transcripts.** Error messages such as
   `You've hit your session limit · resets 3:50am (Europe/Berlin)` or `You've hit your Opus limit · …`, and
   warnings such as `You've used 85% of your session limit`. They calibrate the caps.
4. **Self-calibration.** While official numbers are fresh, `limits.py` learns how many units make 1 % of each limit
   and uses that scale when the snapshot gets stale (`cap: calibrated`). See [Self-calibration](#self-calibration).
5. **Config** `~/.claude/claude-orchestrator/limits.json` overrides caps, weights, thresholds and the context window.

Not seen by the scripts: usage from other devices, claude.ai chats, or another `CLAUDE_CONFIG_DIR`. An older v1
directory is still read as a fallback — see [Migrating from v1](#migrating-from-v1).

## Usage units

```
units = model_weight × ( input + 5·output + 0.1·cache_read + 1.25·cache_write_5m + 2·cache_write_1h )
```

Cache writes without a 5m/1h breakdown are counted as 5m. Default weights (relative cost per family, `model_weights`):
fable 2.0, opus 1.0, sonnet 0.6, haiku 0.2, other 1.0. The family is found by substring in the model id (`fable`,
`opus`, `sonnet`, `haiku`). `costs.py` uses exactly the same units.

## Windows and caps

- **Session blocks.** Usage is grouped into 5-hour blocks starting at the first request after the previous block ended.
  When a limit message gives a reset time, the block is pinned to `[reset − 5 h, reset)`. With official numbers the
  window is the official one.
- **Week.** Rolling 7 days (or the official weekly window when calibrated).
- **Session cap from real events.** For each real session-limit event, the units consumed in the 5 hours before the hit
  are a cap sample. For each `used N%` warning (N above 20), `units / N` is a sample. The largest sample wins
  (`cap: observed-limit`).
- **Before any hit.** The cap is the largest completed past block (`cap: history-max`) — a low-confidence guess.
  With no completed block there is no cap and no percentage.
- **Weekly and per-model caps** are calibrated the same way from weekly / `Opus limit` / `Fable limit` events and
  warnings, over the preceding 7 days.
- **Config wins** over the estimates: `session_cap_units`, `weekly_cap_units` and `model_weekly_cap_units` take priority
  (`cap: config`).
- **Reset time parsing** understands forms like `resets 3:50am (Europe/Berlin)`, a weekday, or a month and day;
  an unknown time zone is treated as UTC.

What the `cap:` value in the `session 5h` line tells you:

| `cap:` | Where the 5-hour percentage comes from |
|---|---|
| `statusline` | The official percentage from a fresh status-line snapshot. |
| `config` | You pinned `session_cap_units`. |
| `calibrated` | The scale learned from earlier official readings ([Self-calibration](#self-calibration)). |
| `observed-limit` | A cap measured from a real limit error or a "used N %" warning in your transcripts. |
| `history-max` | The largest completed past block — a low-confidence guess. |

When several apply, they are used in this order: `statusline`, `config`, `calibrated`, `observed-limit`, `history-max`.

## Self-calibration

Official numbers exist only while the status line is running, and only for Pro/Max subscribers. Self-calibration lets
the orchestrator keep that scale in the gaps: when the snapshot is older than 10 minutes — for example during a long
wave of background agents, or in a terminal that runs without the status line.

**How it works.**

1. Whenever `limits.py` runs while the status-line snapshot is fresh, it counts the units you used inside the official
   5-hour window and divides them by the official percentage. That is how many units make 1 % of the 5-hour limit. It
   does the same for the 7-day window.
2. The scale is stored in `calibration.json` together with the percentage it was learned at, the time, the end of the
   official window and the `model_weights` it was computed with. A newer reading replaces the older one. Readings below
   3 % are ignored, and below 10 % only a first reading is accepted — integer percentages are too coarse at a low fill.
3. When there is no fresh snapshot, `limits.py` uses the stored scale instead of a cap guessed from past blocks or
   limit events. The cap becomes units per 1 % × 100, and while the stored official window is still running, usage is
   counted from the start of that window rather than from the locally guessed block. The weekly window is rolled
   forward in steps of 7 days from the stored reset moment.

**What `cap: calibrated` means.** The percentage is still an estimate, but one anchored to your last official reading
instead of to past blocks and limit events. The report then says `source: calibrated+transcripts` and prints
`calibration 5h: 1% ≈ … units (learned at …)`. The same scale turns `costs.py` units into "≈ % of the 5-hour limit" and
makes `%` budgets possible ([Plan budgets](#plan-budgets)).

**When it is not used.** The config wins: with `session_cap_units` or `weekly_cap_units` set, that cap stays. A scale
older than 14 days is ignored, and so is one learned under different `model_weights` — units are comparable only under
the same weights. Fresh official numbers always win over the scale.

**What it cannot see.** The usage and the scale both come from this machine's transcripts. Usage on other devices, in
claude.ai or under another `CLAUDE_CONFIG_DIR` never reaches them. Between refreshes such hidden usage is missing from
the estimate, and if it was running while the scale was learned, it skews the scale too — so treat `cap: calibrated`
figures as an approximation. The next fresh official reading replaces the estimate and refreshes the scale.

## Levels

The level (`mode`) is derived from the larger of the session and weekly percentages (official when available).

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
| Fable `economy` | Fable only as judge of critical/protocol decisions; other Fable roles → Opus max |
| Opus `off` | senior roles → Sonnet with effort high (or Fable if available); reviews sequential |
| Sonnet `off` | analysis and docs → Haiku high or Opus medium (from the reference policy; `limits.py` does not currently print a directive for it) |

Fable is switched off first when the session budget gets tight because it is the most expensive. Per-call `effort`
requires Claude Code 2.1.292 or newer. `model: best` in agent files means Fable if the account has it, otherwise
Opus. Without Fable access, the Fable rows never apply in practice. A model reaches `economy` or `off` through its
weekly share only when a cap is known for it — from `model_weekly_cap_units` in the config, or from a recorded limit
event or warning for that model; otherwise its percentage reads `n/a` and only the session level can move it.

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

Fill comes from the status-line snapshot when it belongs to the same session (or when no transcript is found), with
the percentage and window size Claude Code reports. Otherwise it comes from the newest transcript of the current
directory's project (last non-sidechain assistant response: input + cache read + cache write + output tokens), and the
window is `--context-window`, else `context_window` from the config, else 200k (1M if more than 200k was ever
observed or the model id contains `[1m]`).

After `/compact`, `/clear` or resume, the `SessionStart` hook runs `checkpoint.py --hook`: it picks the newest
`.claude/plans/*.md` whose header has `Status: in-progress`, and prints its first 12 lines, the `## Checkpoint` section
(up to 80 lines) and the current limits line. Claude Code adds that output to the new context. No in-progress plan:
the hook prints nothing. A brand-new session (`startup`) does not get this injection — use `/orchestrator:resume`.

The dashboard behind `/orchestrator:status` is `checkpoint.py --status`: plan progress, the checkpoint excerpt, the
limits report and the costs.

```
[orchestrator] status — plan .claude/plans/2026-05-04-password-reset.md (in-progress)
progress: 4 done · 2 in progress · 3 to do  ■■■■◧◧□□□ 44%
```

Optional tuning (Claude Code settings, not this plugin): `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`,
`CLAUDE_CODE_AUTO_COMPACT_WINDOW`.

## Costs

`costs.py` turns the same transcripts into a cost report: how many tokens and usage units each role and each agent
spent, and what share of your limits that is. In Claude Code, `/orchestrator:costs` runs it and adds a short summary
with one saving tip.

```bash
python3 skills/orchestrator/scripts/costs.py                       # the current session and its subagents
python3 skills/orchestrator/scripts/costs.py --project-wide --since 2026-05-04T09:00
python3 skills/orchestrator/scripts/costs.py --plan .claude/plans/2026-05-04-password-reset.md
```

| Option | Meaning |
|---|---|
| *(none)* | The current session: the newest transcript of this project and its subagents. |
| `--session <id or path>` | Another session: an id (a prefix is enough) or a transcript path. |
| `--project-wide` | Every session of this project (use it with `--since`); includes runs started by `spawn.sh`. |
| `--since ISO` | Count only usage after this moment (local time when there is no offset). |
| `--plan FILE` | Check a plan's budget ([Plan budgets](#plan-budgets)). Implies project-wide counting since the plan's start. |
| `--active-plan` | Use the newest in-progress plan as `--plan`. |
| `--budget-only` | Print only the budget line; silent when there is no budget. |
| `--top N` | How many top agents to list (default 8). |
| `--json` | Machine-readable report. |
| `--hook [EVENT]` | Hook mode: silent unless the active plan crossed 80 % / 100 % of its budget. |
| `--config FILE` | Limits config to take the model weights from. |

**What units are.** Tokens weighted by what they cost, so that different models and kinds of tokens can be added up:
output tokens count 5×, cache reads 0.1×, cache writes 1.25× (5-minute) or 2× (1-hour), and every model family has its own
weight (Fable 2.0, Opus 1.0, Sonnet 0.6, Haiku 0.2). The formula is under [Usage units](#usage-units).

The report:

```
Costs — session 3f2a9c1e · since 2026-05-04 09:52Z · 412 responses
  total: 61.2M tokens · 8.47M units · ≈ 18.4% of the 5-hour limit · ≈ 3.4% of the week

  role                         agents   model   tokens    units   ≈5h %  share
  orchestrator (main)               1    opus    24.1M    3.52M    7.7%    42%
  orch-dev-senior                   2    opus    19.8M    2.61M    5.7%    31%
  orch-reviewer                     2    opus    9.40M    1.37M    3.0%    16%
  orch-tech-writer                  1  sonnet    3.10M   402.5k    0.9%     5%
  orch-security                     1   fable    1.20M    388.0k    0.8%     5%
  orch-scout                        3   haiku    3.60M   121.0k    0.3%     1%
  orch-build-verifier               2   haiku   0.20M    14.2k     0.0%     0%

  top agents:
    orch-dev-senior        a3de429a5d    1.52M units  opus   API + web client for password reset
    orch-reviewer          a0bfb4ae2d    0.81M units  opus   Review backend changes

  budget (2026-05-04-password-reset.md): 25% of the 5-hour limit → spent 18.4% = 74% → OK
```

| Column | Meaning |
|---|---|
| `role` | The subagent type (`orch-reviewer`), `orchestrator (main)` for the conversation itself, or `subagents (inline)` for sidechain replies recorded in the main transcript. |
| `agents` | How many separate agents of that role ran. |
| `model` | The model family that spent most of that role's units. |
| `tokens` | Every token: input, output, cache reads and cache writes. Cache reads are numerous but cheap, which is why tokens run several times above units. |
| `units` | The same tokens weighted by price — the [usage units](#usage-units) above. |
| `≈5h %` | Units divided by the units that make 1 % of the 5-hour limit. Needs a calibration ([Self-calibration](#self-calibration)); the week figure in the header works the same way. |
| `share` | The role's share of all units. |

**How roles are detected.** Claude Code stores each subagent's transcript next to the session
(`<session>/subagents/agent-<id>.jsonl`) with an `agent-<id>.meta.json` beside it. `costs.py` reads `agentType` from
that meta file (`orchestrator:orch-reviewer` is shown as `orch-reviewer`) and the `description` the agent was launched
with, which appears under "top agents". A subagent without a meta file is listed as `subagent`. Responses are
de-duplicated by message id, so nothing is counted twice, and agents that spent nothing are not listed.

**Without a calibration** the `≈ %` columns read `n/a` and the report adds a note: they appear after the status line has
reported official numbers at least once.

## Plan budgets

A plan can limit its own spend. Put a `Budget:` line and a `Started:` line in the plan header (only the first 4000
characters of the file are read); the template [`templates/plan.md`](../../skills/orchestrator/templates/plan.md) has
both:

```
**Date:** 2026-05-04 · **Status:** in-progress
**Started:** 2026-05-04 09:52 · **Budget:** 25%
```

| Header | Meaning | Needs a calibration |
|---|---|---|
| `Budget: 25%` | 25 % of the 5-hour limit | yes |
| `Budget: 4M tokens` | 4 million tokens (`k` and `M` suffixes are understood; a bare number counts as tokens) | no |
| `Budget: 2.5M units` | 2.5 million [usage units](#usage-units) | no |

Tokens here include cache reads, so a token budget fills faster than the limit does; a `%` or `units` budget follows
the real consumption of the limit more closely.

**What is counted.** Every session of the project since `Started:` — `YYYY-MM-DD HH:MM` in local time. Without that
line the `Date:` line is used, and without it the creation time of the plan file. Subagent transcripts and runs started
with `spawn.sh` are included.

**What the hook does.** After every `Agent` tool call the budget hook (`costs.py --hook PostToolUse`) looks at the newest
in-progress plan that has a `Budget:` line and speaks to the orchestrator once when the plan crosses each threshold:

- At 80 % of the budget:
  `[orchestrator budget] plan .claude/plans/2026-05-04-password-reset.md: 82% of the budget (25% of the 5-hour limit) spent. Prefer cheaper models, avoid optional reviews and scope growth; tell the user if the rest will not fit.`
- At 100 %: the budget is reported as used up, with the instruction not to launch new agents, to finish or checkpoint
  in-flight work and to ask you whether to extend the budget.

It is silent when there is no in-progress plan, no `Budget:` line, or a `%` budget without a calibration yet (the
level reads `UNKNOWN` — enable the status line once). To extend a budget, edit the line in the plan.

**Checking by hand.** `costs.py --plan <plan.md>` prints the report scoped to that plan; `costs.py --active-plan
--budget-only` prints just the budget line of the newest in-progress plan.

## Hooks

`hooks/hooks.json` registers four hooks (three Claude Code events; `SessionStart` has two matchers). Hooks put
instructions into the orchestrator's context; they never block a tool call. Silent when all is fine.

| Event | Command | Effect |
|---|---|---|
| `SessionStart` (`startup`) | `scripts/sync_stable.py` | Refreshes the stable copy of the scripts after a plugin update (below). |
| `SessionStart` (`compact\|resume\|clear`) | `checkpoint.py --hook` | Re-injects the plan checkpoint and a limits line. |
| `PostToolUse` (`Agent`) | `limits.py --hook PostToolUse`<br>`costs.py --hook PostToolUse` | After each agent launch or finish: a limits directive if the state degraded or changed; a budget alert at 80 % / 100 %. |
| `UserPromptSubmit` | `limits.py --hook UserPromptSubmit --cache-sec 120` | The same limits directive, once per prompt. |

**Limits hook.** It keeps the last state (mode, per-model statuses, context status) in
`~/.claude/claude-orchestrator/last-state.json` and speaks only when it changed — including when the state recovers. The
first call stays silent if everything is fine. Reports are cached in `last-report.json` for `--cache-sec` seconds (60
by default, 120 for `UserPromptSubmit`), so the transcripts are not rescanned on every call. The hook reads the
transcript path from the hook's input to find the current conversation. Any exception is printed to stderr and the hook
exits 0, so it cannot break a session. The message looks like:

```
[orchestrator limits] mode=economy session=63% week=47% context=41% models=fable:ok,haiku:ok,opus:ok,sonnet:ok :: ECONOMY: max 2 parallel heavy agents; no refute panels; prefer haiku for search/build, sonnet for analysis; reviews only for risky changes.
```

`--always` forces output even if unchanged. The budget hook keeps its own state in `costs-state.json`.

**Startup sync of the stable copy.** The status line command, and the hooks of a manual install, must not point into
the plugin's own directory, because that directory changes with every version. They run a stable copy in
`~/.claude/claude-orchestrator/` instead. At the start of each session `sync_stable.py` compares that copy
(`limits.py`, `statusline.py`, `checkpoint.py`, `costs.py`) with the plugin's scripts and refreshes whatever differs —
but only if you have set the status line up (`statusline.py` is present there). It is silent and ignores errors.

**Manual installs.** Add `--hooks` to `install.sh`: it registers the checkpoint, limits and budget hooks in
`settings.json`, pointing at `~/.claude/claude-orchestrator/`. The startup sync is plugin-only; after `git pull`, run
`./install.sh` again to refresh the copy. Do not combine a plugin with `--hooks`, or every hook fires twice.

## Status line

`statusline.py` prints one line and saves the snapshot described above:

```
Opus 5.5 · ctx 41% · 5h 63% ↻14:50 · 7d 22%
```

The `5h` and `7d` parts appear only if Claude Code supplies `rate_limits` (Pro/Max); `ctx` appears whenever the
context percentage is available; `↻` is the local reset time.

**Set it up once.** A plugin cannot ship a status line, so enable it:

```
/orchestrator:setup                  # plugin install, typed in Claude Code
./install.sh --statusline            # manual install
```

`/orchestrator:setup` runs `install.sh --statusline-only`. It copies the scripts to `~/.claude/claude-orchestrator/`,
adds a `statusLine` entry to `~/.claude/settings.json` and makes a backup `settings.json.bak-<time>` first. The line
appears after your next message (restart Claude Code if it does not); `5h` and `7d` show up on Pro/Max after the first
reply. After a plugin update the copy of the scripts refreshes itself at the next session start.

**An existing status line is kept.** Its command is stored in `ORCH_STATUSLINE_NEXT` inside the new command, and its
output is appended after ` | ` (5-second timeout). Setting it up again is safe: the chain is preserved. To wire it by
hand, put this into `settings.json` with an absolute path:

```json
"statusLine": { "type": "command", "command": "python3 /ABS/PATH/statusline.py" }
```

**Undo.** Type `/orchestrator:setup remove` before you uninstall the plugin. It removes only Orchestrator's status line
and hook entries and restores your previous status line (a backup of `settings.json` is kept); the data folder
`~/.claude/claude-orchestrator` (calibration, an optional `limits.json`) stays. For manual installs `./uninstall.sh`
removes the entries, the data folder, the skill and the agents.

## Configuration

File: `~/.claude/claude-orchestrator/limits.json`, or the path in `$ORCH_LIMITS_CONFIG`, or `--config <file>`. The
first one that exists is used, in the order `--config`, `$ORCH_LIMITS_CONFIG`, the default file; its keys are merged
over the defaults (nested objects are merged key by key). Template:
[`examples/limits.example.json`](../../examples/limits.example.json).

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
recorded, or if the estimate keeps being off. It also stops self-calibration from replacing the cap.

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

Changing `model_weights` also discards the stored calibration, which is then learned again.

## Data directory and environment

Everything the scripts write lives in `~/.claude/claude-orchestrator/` (under `CLAUDE_CONFIG_DIR` if set):

| File | What it is |
|---|---|
| `statusline.json` | The latest official snapshot written by the status line; read only if younger than 10 minutes. |
| `calibration.json` | The learned units per 1 % of the 5-hour and weekly limits. |
| `limits.json` | Your optional configuration. |
| `last-state.json`, `last-report.json` | State and cache of the limits hook. |
| `costs-state.json` | The last budget level reported per plan. |
| `limits.py`, `statusline.py`, `checkpoint.py`, `costs.py` | The stable copy of the scripts (after status line setup or a manual install). |

Environment variables: `CLAUDE_CONFIG_DIR` (where Claude Code keeps its data; default `~/.claude`),
`ORCH_LIMITS_CONFIG` (path to a limits config), `ORCH_STATUSLINE_NEXT` (command of another status line to chain),
`CLAUDE_PROJECT_DIR` (set by Claude Code for hooks; `costs.py` and `checkpoint.py` use it to find the project).

## Troubleshooting

**The mode is `economy` (or `critical`) but I have not hit any limit.** Before the first recorded limit event the cap
is the largest completed past block (`cap: history-max`). If the current block is larger than every earlier one, the
percentage is over 100 % by construction, and a small history makes the cap too low. Run `limits.py` and check `cap:`.
Fixes: enable the status line (Pro/Max) so official percentages and the calibrated scale are used; set
`session_cap_units`; or raise `thresholds`.

**`cap: history-max` and `n/a` percentages.** No completed block in the last 8 days yet; there is nothing to compare
with. The mode stays `normal` until data accumulates (context checks still work).

**`/orchestrator:limits` says the source is `transcripts` only.** Nothing official has reached it. On Pro/Max, turn on the
status line (`/orchestrator:setup`) to get exact numbers; with an API key you keep the estimates.

**Status line is blank.** Check the settings: `statusLine` must point at an existing `statusline.py` (`python3` in
`PATH`). Claude Code only runs a status line command after the workspace is trusted, so accept the trust dialog for
the folder first. Run `echo '{}' | python3 ~/.claude/claude-orchestrator/statusline.py` — it should print a line.
This trust requirement comes from Claude Code, not from this package; see the Claude Code documentation.

**No `5h` / `7d` in the status line.** `rate_limits` is supplied only for Pro/Max subscribers, and only after the first
reply of a session. Otherwise the estimates from transcripts are used.

**After a plugin update the status line runs old code.** The copy in `~/.claude/claude-orchestrator/` refreshes at the next
session start; run `/orchestrator:setup` again to refresh it right away.

**`context` shows `unknown`.** No transcript was found for the current directory and the status-line snapshot is
older than 10 minutes or from another session. Enable the status line, or pass `--session-file`.

**Percentages disagree with `/usage`.** Expected: estimates cover only this machine's transcripts and use a fixed
price structure ([What it cannot see](#self-calibration)). Trust the official numbers; pin caps in config if you want
estimates close to them.

**`costs.py` shows `n/a` in the `≈ %` columns, or a budget reads `UNKNOWN`.** There is no calibration yet. Enable the
status line on a Pro/Max plan and let `limits.py` run once while the snapshot is fresh (any hook does that); `tokens` and
`units` budgets work without it.

**The limits hook never speaks.** By design it is silent while everything is `normal`/`ok` and nothing changed. Check
`~/.claude/claude-orchestrator/last-state.json`, or run `limits.py --hook --always`.

**The budget hook never speaks.** It needs an in-progress plan with a `Budget:` line in the first 4000 characters, and
it speaks only when the 80 % or 100 % line is crossed (once each). Check with `costs.py --active-plan --budget-only`.

**Hooks fire twice.** You installed the plugin and also ran `install.sh --hooks`. Delete the `hooks` entries that mention
`claude-orchestrator` from `~/.claude/settings.json`, or run `./uninstall.sh` (it removes the whole manual install,
status line included — then run `/orchestrator:setup` again).

**Python version.** Needs 3.9+ (`zoneinfo`); on older versions time zones in reset texts fall back to UTC.

## Migrating from v1

The product was called Team Orchestrator (plugin `team-orchestrator`) before 2.0.0. What changes for limits and data:

- **Data directory.** Everything now lives in `~/.claude/claude-orchestrator/` instead of `~/.claude/team-orchestrator/`.
  The old directory is still read as a fallback — for `limits.json`, and for the status-line snapshot (the fresher of
  the two wins, so an old v1 status line keeps feeding the new scripts until you switch). The new scripts write only to
  the new directory. Calibration starts from scratch and is learned again as soon as the status line reports official
  numbers.
- **Hooks.** The hooks of a plugin install go away with the v1 plugin. Entries that a manual v1 install put into
  `settings.json` are replaced when you run `./install.sh --hooks` of the new version, and removed by its
  `./uninstall.sh`.
- **Status line.** Run `/orchestrator:setup` (plugin) or `./install.sh --statusline` (manual) once: it points
  `settings.json` at the new directory and keeps the status line you had chained behind the old one. A backup is made
  first.
- **Cleanup.** When the new status line works, copy a `limits.json` you want to keep to the new directory and delete the
  old one:

```bash
mkdir -p ~/.claude/claude-orchestrator
cp ~/.claude/team-orchestrator/limits.json ~/.claude/claude-orchestrator/   # only if you had one
rm -rf ~/.claude/team-orchestrator
```

The renames (plugin, marketplace, commands, agents) and the plugin migration steps are in the
[usage guide](usage-guide.md#migrating-from-v1).
