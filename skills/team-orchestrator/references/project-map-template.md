# Project map template (`.claude/orchestrator/project-map.md`)

Built by `orch-scout` on first use, kept current by the orchestrator. Keep it ≤ 150 lines — it is read often.

```markdown
# Project map — <name>   (updated YYYY-MM-DD)

## What it is
One paragraph: purpose, components, how they talk.

## Components and sizes
| Area | Path | Size | Language/stack | Notes (monoliths, generated code) |

## Commands (verification ladder uses these)
- build: …        - tests: …        - lint/typecheck: …
- run locally: …  - per platform: …  (exact working directory, env vars like JAVA_HOME)

## Specs, protocols, docs worth knowing
| Doc | When to read | How (ranges, not whole files) |

## Production (read-only facts)
host/region, service names, deploy method, health endpoint, backup/rollback practice, who approves.

## Traps
Known flaky tests, build quirks, tools that must not be used, paths with spaces, generated files.
```
