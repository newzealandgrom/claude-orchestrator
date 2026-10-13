# Verification ladder

Never close a step on the developer's word. Verification is proportional to risk.

| Change touches | Required checks |
|---|---|
| anything | `orch-build-verifier`: compile/build/tests/linters of every affected area (commands from the project map) |
| code written by middle/senior | `orch-reviewer` — adversarial: tries to refute "done", runs the build, checks acceptance criteria |
| crypto, keys, tokens, signatures, wire formats, cross-platform compatibility | `orch-protocol-reviewer` — test vectors on real code of every platform pair, negative cases |
| auth, rate limits, IP/proxy trust, perimeter, production config | `orch-security` |
| user-visible flows, new UI | `orch-qa` — scenarios + manual checklist for devices |
| Critical findings or irreversible protocol decisions | refute panel: 3 independent reviewers (different models/lenses); accept at ≥ 2 "not refuted" |

## Fix loop

1. Reviewer verdict "rework" → send the findings to the **same** developer agent with `SendMessage` (it keeps its
   context; cheaper and better than a new brief).
2. Ask the reviewer to re-check **only the fixes** (resume it with `SendMessage`) — a short "round 2".
3. Repeat until accepted or until the remaining items are consciously deferred and documented.
4. Fixes often introduce new bugs (a fix for a bypass opens another bypass) — the round-2 review is mandatory
   for security-relevant fixes.

## Cross-platform protocols

- Generate reference vectors with an independent implementation (e.g. Python) and verify them independently
  before handing them out. Every platform must decrypt/parse the vector and match field by field.
- For JSON-in-ciphertext formats compare decrypted bytes and parsed fields, not ciphertext.
- Run a cross matrix (each encoder → each decoder) on real code before declaring compatibility.
- Pin validation semantics explicitly (required fields, limits, units like ms vs s, unicode categories) — drift
  between platforms is the most common defect.

## Before reporting "done"

- Final build-verify of all areas on the merged tree.
- Flaky tests: determine whether flakiness is in the code or the test; fix the test if it is the test.
- Report verification as commands → results; say what was not verified (e.g. "not tested on devices").
