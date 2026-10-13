# Model routing and token economy

Goal: the lowest cost **at the same quality**. Save on search, reading and mechanics — not on decisions and checks.

## Tiers

| Model | Strong at | Use for | Do not use for |
|---|---|---|---|
| Fable (`best` = Fable if available, else Opus) | hardest reasoning, security, protocols | architecture of cross-cutting changes, protocol/crypto review, threat modelling, judge of critical disputes | search, mechanical edits, builds, docs |
| Opus | complex code, reviews, operations | senior dev, adversarial reviewer, devops, designer | single-file tasks with an exact spec |
| Sonnet | solid implementation from a spec, analysis, writing | middle dev, analyst, QA, tech writer, toolsmith | crypto, protocol, multi-platform edits |
| Haiku | fast and cheap | scout, build-verifier, junior (exact diff) | anything that needs a decision |

## Effort

`low` mechanics · `medium` standard work · `high` senior code, reviews, architecture, security ·
`xhigh`/`max` single judges of critical findings, irreversible protocol decisions, and **Fable fallbacks on Opus**.

## Rules

1. Size first: S tasks — do it yourself.
2. Recon with Haiku (`orch-scout`), pass its map in briefs — expensive agents must not search.
3. Ranges, not files: always `file:A-B` and the `sed -n` command; never hand a 4 000-line file to anyone.
4. One writer per file.
5. Escalate, do not start high: Haiku → Sonnet → Opus → Fable, same brief + the failure reason.
6. Structured outputs (role formats, JSON schemas in workflows). Prose is waste.
7. Verification proportional to risk (see `verification.md`).
8. Do not duplicate: reuse maps, snapshots and plans.
9. Fan-out: ≤ 4 heavy agents at once in `normal`, ≤ 2 in `economy`, 0 new in `critical`.
10. The orchestrator's context is the most expensive: read digests and reports, not code.
11. Limits gate before every wave: `scripts/limits.py` (see `limits-and-context.md`).

## Overrides at call time

- Agent tool: `Agent(subagent_type: "orch-architect", model: "opus", effort: "max", prompt: …)`.
- Separate process: `scripts/spawn.sh orch-architect brief.md --model opus --effort max`.
- Precedence: per-call `model` > agent frontmatter > `CLAUDE_CODE_SUBAGENT_MODEL` > main model
  (`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` blocks overrides).

## Rough cost guide (tokens per agent)

scout 5–50k · build-verifier 5–30k · junior 10–30k · middle 30–100k · senior 60–500k · reviewer 40–300k ·
architect/protocol/security 60–300k. A plan with five dev steps and full verification: 0.5–1.5M; a cross-platform
protocol change with review rounds: 3–7M. Write the estimate into the plan and compare with the result.
