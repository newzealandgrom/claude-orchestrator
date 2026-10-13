# Team Orchestrator for Claude Code

[Русская версия](README.ru.md)

A Claude Code plugin that turns a non-trivial request into a plan, hands the steps to role subagents (architect,
developers, reviewers, security, QA, ...) on the right model and effort, verifies the results, and reports — while
watching your usage limits and the orchestrator's own context.

## Why

- **Context is the expensive part.** A long session that reads files itself burns its context window. The
  orchestrator delegates reading and editing to subagents and works from short `file:line — fact` reports.
- **Wrong model for the job.** Searching a repo on the strongest model, or designing a protocol on the cheapest one,
  both waste something. Each role has a default model and effort; the orchestrator escalates only on failure.
- **Hitting limits mid-task.** Before every wave of agents the orchestrator runs a limits gate
  (`scripts/limits.py`) and switches to economy mode, stops launching agents, or re-routes Fable roles to Opus
  with `effort: max` when needed.
- **Losing state on `/compact`.** The plan file keeps a `## Checkpoint` section; a `SessionStart` hook re-injects it
  after `/compact`, `/clear` or resume, so work continues from facts rather than a lossy summary.

## Features

- One skill (`team-orchestrator`) and 15 role subagents (`orch-*`) — see [Roles](#roles).
- Size triage: small tasks are done directly, only M/L tasks are orchestrated.
- Plans in `.claude/plans/` from a template, with per-step role, model/effort, acceptance criteria and a
  verification command.
- Verification ladder: build-verifier, adversarial reviewer, protocol/crypto reviewer, security, QA; refute panel
  for critical findings.
- Limits gate: 5-hour session, rolling 7 days and per-model status, with automatic Fable -> Opus (`effort: max`)
  fallback.
- Context management: checkpoints at 50 % and a `/compact` request at 75 % of the context window.
- Parallel work without collisions: one writer per file, git worktrees for parallel writers in one build tree.
- Production gate: nothing is deployed, pushed or deleted without your explicit "yes" for that step.
- Clean-context agent processes via `spawn.sh` / `collect.sh`.
- Optional status line: `model · ctx 41% · 5h 63% ↻14:50 · 7d 22%`.

## How it works

```
 you: "/team-orchestrator <task>"
   |
   v
 orchestrator skill ---- size: S -> do it directly
   |                     M/L -> continue
   v
 limits gate (scripts/limits.py)  -> mode / per-model status / context fill / actions
   |
   v
 plan (.claude/plans/<date>-<slug>.md, with ## Checkpoint)
   |
   v
 role agents (orch-scout, orch-dev-*, orch-architect, ...)  <- briefs from templates/brief.md
   |                                                           (limits gate before every wave)
   v
 verification (build-verifier, reviewer, protocol-reviewer, security, qa)
   |
   v
 production gate (only with your explicit "yes")  ->  report: what changed, how verified, what is left
```

## Quick start

Inside a Claude Code session:

```
/plugin marketplace add newzealandgrom/claude-orchestrator
/plugin install team-orchestrator@team-orchestrator
```

Or in one step (Claude Code 2.1.275 or newer):

```
/plugin install team-orchestrator --marketplace newzealandgrom/claude-orchestrator
```

From a shell:

```bash
claude plugin marketplace add newzealandgrom/claude-orchestrator
claude plugin install team-orchestrator@team-orchestrator            # add --scope user|project|local if needed
# one-step variant (Claude Code 2.1.292 or newer):
claude plugin install team-orchestrator --marketplace newzealandgrom/claude-orchestrator
```

A plugin cannot ship a status line, so enable it separately (optional, recommended):

```bash
git clone https://github.com/newzealandgrom/claude-orchestrator.git
cd claude-orchestrator
./install.sh --statusline-only
```

This copies `limits.py`, `statusline.py` and `checkpoint.py` to `~/.claude/team-orchestrator/` and patches
`~/.claude/settings.json` (a backup `settings.json.bak-<timestamp>` is made first). An existing status line is kept
and appended through `ORCH_STATUSLINE_NEXT`.

First use:

```
/team-orchestrator fix the failing tests in api/ and add coverage
```

The skill is available as `/team-orchestrator:team-orchestrator`; the short `/team-orchestrator` works unless
another command has the same name. Agents are addressed as `team-orchestrator:orch-<role>`. To continue an
unfinished plan: `/team-orchestrator resume`.

## Manual install (without the plugin system)

```bash
git clone https://github.com/newzealandgrom/claude-orchestrator.git
cd claude-orchestrator
./install.sh                          # skill + agents for your user (~/.claude)
./install.sh --project <dir>          # skill + agents for one project (<dir>/.claude)
```

Flags: `--statusline` (also enable the status line), `--hooks` (also register the three hooks — not needed for
plugin installs), `--statusline-only` (plugin users), `--dry-run` (show what would change). `settings.json` is backed
up before any change. `CLAUDE_CONFIG_DIR` is honoured.

Requirements:

- Claude Code; 2.1.292 or newer recommended (per-call `effort` override used for the Fable -> Opus fallback).
- Python 3.9+, standard library only.
- macOS or Linux. The `terminal` and `interactive` spawn modes need macOS Terminal; `tmux` mode needs tmux.
- Fable access is optional: agents with `model: best` use Fable if the account has it, otherwise Opus.

## Roles

Defaults live in the agent frontmatter (`agents/orch-*.md`); `best` = Fable if available, otherwise Opus.

| Role | Agent | Model / effort | Purpose |
|---|---|---|---|
| Architect / tech lead | `orch-architect` | best / high | Plan or spec review for large tasks, second opinion, judge. Read-only. |
| Analyst | `orch-analyst` | sonnet / high | Vague request -> requirements and acceptance criteria; docs-vs-code drift. Read-only. |
| Senior developer | `orch-dev-senior` | opus / high | Cross-cutting, protocol, security-sensitive, multi-module changes. |
| Middle developer | `orch-dev-middle` | sonnet / medium | Well-specified change inside one module. |
| Junior developer | `orch-dev-junior` | haiku / medium | Mechanical work by exact instruction: diffs, renames, imports. |
| DevOps / SRE | `orch-devops` | opus / medium | Production snapshots, deploy plans with rollback; acts only with `OWNER_APPROVED: yes`. |
| Security / pentest | `orch-security` | best / high | Threat model, auth, perimeter, rate limits; non-destructive checks of your own systems. Read-only. |
| Protocol / crypto reviewer | `orch-protocol-reviewer` | best / high | Key schemes, wire formats, versioning, cross-platform test vectors. Read-only. |
| Adversarial reviewer | `orch-reviewer` | opus / high | Tries to refute "done" for a dev step; runs the build. Read-only. |
| QA / user voice | `orch-qa` | sonnet / medium | Scenarios, smoke checklists, UX traps; builds and runs, does not edit code. |
| Build verifier | `orch-build-verifier` | haiku / low | Runs the listed commands, returns PASS/FAIL with error lines. |
| Scout | `orch-scout` | haiku / low | `file:line — what` maps; navigates large documents. Read-only. |
| Designer / frontend | `orch-designer` | opus / medium | Design tokens, screens, components, accessibility, microcopy. |
| Tech writer | `orch-tech-writer` | sonnet / medium | README, changelogs, runbooks; every claim checked against code. |
| Toolsmith | `orch-toolsmith` | sonnet / medium | Finds and vets plugins/skills/MCP/LSP; returns install commands, never installs. |

Typical teams and details: `skills/team-orchestrator/references/roles.md`.

## Limits and context

Details: [docs/en/limits-and-context.md](docs/en/limits-and-context.md).

`python3 skills/team-orchestrator/scripts/limits.py` (about 1 s, local, read-only) prints the routing state. The
orchestrator runs it first and before every wave of agents.

| Level | Trigger | What changes |
|---|---|---|
| normal | below 60 % of the tightest window | up to 4 heavy (Opus/Fable) agents in parallel, full verification |
| economy | 60 % and above | up to 2 heavy agents, no refute panels, Haiku for search/builds, Sonnet for analysis |
| critical | 80 % and above | no new Opus/Fable agents; finish in-flight work, checkpoint, report done/left and reset time |
| exhausted | 95 % and above, or an active limit error | launch nothing; checkpoint; resume agents with `SendMessage` after the reset |

Before the first real limit hit the cap is only a guess (the largest past block), so levels derived from it are
downgraded by one step (80 % and above gives `economy`, 95 % and above gives `critical`); an actual limit error always
means `exhausted`.

- **Fable fallback:** when Fable is off (its own limit error, weekly share at 85 % of its cap, or session
  `critical`/`exhausted`), every Fable/`best` role runs on Opus with `effort: max`.
- **Context:** at 50 % of the window the plan's `## Checkpoint` is rewritten; at 75 % the orchestrator asks you to run
  `/compact keep: plan <path>, running agents, next step`.
- **Status line** shows model, context fill and — for Pro/Max subscribers only — the official 5-hour and 7-day
  percentages with the reset time. Everybody gets the context percentage.
- **Config:** `~/.claude/team-orchestrator/limits.json` (see [Configuration](#configuration)).

## Hooks

Shipped in `hooks/hooks.json`, active for plugin installs:

| Event | Command | Effect |
|---|---|---|
| `SessionStart` (matcher `compact\|resume\|clear`) | `checkpoint.py --hook` | Re-injects the active plan's `## Checkpoint` and a limits line. |
| `PostToolUse` (matcher `Agent`) | `limits.py --hook PostToolUse` | After an agent call: a directive, only if the state degraded or changed. |
| `UserPromptSubmit` | `limits.py --hook UserPromptSubmit --cache-sec 120` | Same, once per prompt. |

The limits hooks are silent when nothing changed; reports are cached for 60–120 s; a hook error never breaks the
session (it exits 0).

## Clean-context agents

For long or independent work an agent can run in a separate `claude` process without the history of the current
chat. Results go to `<project>/.claude/runs/<run-id>/`.

```bash
S=~/.claude/skills/team-orchestrator/scripts   # manual install; for a plugin use the plugin's skills/team-orchestrator/scripts

# brief from a file, headless background process
"$S/spawn.sh" orch-scout brief.md --mode headless --id scout-api

# brief from stdin, override model/effort (e.g. Fable is off)
echo "Review api/auth.py:10-120 ..." | "$S/spawn.sh" orch-reviewer - --model opus --effort max

# visible modes: terminal (macOS Terminal), tmux (session "orch"), interactive (macOS)
"$S/spawn.sh" orch-dev-middle brief.md --mode tmux

# status and results
"$S/collect.sh"                       # 20 most recent runs
"$S/collect.sh" scout-api --wait      # wait until the run is done
"$S/collect.sh" scout-api --full      # full result instead of the first 60 lines
```

`spawn.sh` options: `--mode headless|terminal|tmux|interactive`, `--id`, `--model`, `--effort`, `--max-turns`
(default 60), `--schema <file>`, `--perm acceptEdits|default|plan|auto|dontAsk|bypass` (default `acceptEdits`),
`--cwd`. Environment: `ORCH_RUNS`, `ORCH_PERM`, `ORCH_WAIT_MAX`. Proxy and `ANTHROPIC_*` variables of the current shell
are passed to the child through a `0600` file that is deleted after start.

## Configuration

`~/.claude/team-orchestrator/limits.json` (or the path in `$ORCH_LIMITS_CONFIG`, or `--config <file>`; the base
directory follows `CLAUDE_CONFIG_DIR`). All keys are optional; nested objects are merged with the defaults. A
template is in `examples/limits.example.json`.

| Key | Default | Meaning |
|---|---|---|
| `session_cap_units` | `null` | Override the estimated 5-hour cap (usage units). |
| `weekly_cap_units` | `null` | Override the estimated 7-day cap. |
| `model_weekly_cap_units` | `{}` | Weekly cap per model family, e.g. `{"fable": 5000000, "opus": null}`. |
| `model_weights` | fable 2.0, opus 1.0, sonnet 0.6, haiku 0.2, other 1.0 | Relative cost weight per family. |
| `thresholds` | economy 0.60, critical 0.80, exhausted 0.95 | Session/weekly levels. |
| `model_thresholds` | economy 0.60, off 0.85 | Per-model weekly levels. |
| `context_window` | `null` | Tokens. Auto: 200k, or 1M if more was ever observed or the model id has `[1m]`. |
| `context_thresholds` | checkpoint 0.50, compact 0.75 | Context fill levels. |

Example: pin the 5-hour cap and make the orchestrator more cautious.

```json
{
  "session_cap_units": 40000000,
  "thresholds": { "economy": 0.50, "critical": 0.70, "exhausted": 0.90 }
}
```

## Update and uninstall

```bash
claude plugin marketplace update team-orchestrator
claude plugin update team-orchestrator@team-orchestrator

claude plugin uninstall team-orchestrator
```

Manual install: `./uninstall.sh` (or `./uninstall.sh --project <dir>`) removes the skill, the `orch-*` agents,
`~/.claude/team-orchestrator/`, and status line / hook entries that mention `team-orchestrator`; it backs up
`settings.json` and restores the status line that was set before `install.sh`. If you enabled the status line with
`--statusline-only` on a plugin install, run `./uninstall.sh` too — `claude plugin uninstall` does not touch your
settings.

## FAQ

**I have no Fable access.** Nothing to do. `model: best` resolves to Opus. The Fable -> Opus fallback only
matters when Fable is available.

**Does it send data anywhere?** The scripts (`limits.py`, `statusline.py`, `checkpoint.py`) contain no network code;
they read local transcripts under `~/.claude/projects/` (usage counters, model ids, timestamps, limit-error texts) and write small state
files to `~/.claude/team-orchestrator/`. Agents themselves are ordinary Claude Code subagents: they talk to the
Anthropic API like any session, and `orch-toolsmith` / `orch-security` may use web tools when briefed to.

**Linux? Windows?** macOS and Linux are the supported platforms. The scripts are bash and Python; there is no native
Windows support, and WSL has not been tested.

**How accurate are the limit estimates?** Approximate. Anthropic does not publish the exact caps; the script
converts token counters into weighted units and calibrates caps from limit errors it finds in your transcripts. Real
numbers (`rate_limits`) are used only when the status line is enabled and you are a Pro/Max subscriber. Treat the
levels as a safety net, not as accounting.

**Why can't it run `/compact` itself?** `/compact` and `/clear` are user commands; a model cannot invoke them. The
orchestrator writes the checkpoint and asks you; the `SessionStart` hook restores it afterwards.

## Contributing

Issues and pull requests are welcome. Before submitting:

```bash
claude plugin validate --strict .
```

Bump `version` in `.claude-plugin/plugin.json` for any user-visible change and add a line to `CHANGELOG.md`.
Keep the scripts standard-library only (Python 3.9+).

## Documentation

- [Usage guide](docs/en/usage-guide.md)
- [Limits and context](docs/en/limits-and-context.md)

## License

MIT, see [LICENSE](LICENSE).
