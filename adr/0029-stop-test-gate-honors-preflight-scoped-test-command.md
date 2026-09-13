---
status: accepted
date: 2026-09-13
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [core-guardrails/hooks/scripts/Stop/vendor/test-gate.mjs, core-guardrails/hooks/scripts/Stop/20_test_gate.py]
supersedes: []
superseded-by: []
---

# ADR-0029 — The Stop-level test gate honors `preflight.toml [commands].test`

## Context and Problem Statement

Since ADR-0027 the `test-gate` concern has two enforcement points that read one mode key:
the PostToolUse per-edit gate (`PostToolUse/10_test_gate.py`) and the Stop-level full-suite
gate (`Stop/20_test_gate.py` → vendored `vendor/test-gate.mjs`). The per-edit gate runs the
repo's own scoped command from `preflight.toml [commands].test`. The Stop gate does not: the
vendored script autodetects `swift test` / `cargo test` / `npm test --silent` and ignores
`preflight.toml` entirely, while the Python wrapper's own comment tells a repo whose suite
needs longer than the 160 s budget to "keep it on a scoped preflight.toml [commands].test" —
advice the runtime never acts on.

Measured on 2026-09-13 in `personal-web-2025` (test-gate `enforce` on this machine): `npm test`
is `vitest run && playwright test`; the Playwright half is a 5-browser matrix plus two extra
Vite builds and preview servers. It cannot finish inside 160 s on any machine, and it also
failed for a second reason (Playwright 1.60 browser builds not installed). Result: the Stop
gate blocked a session whose only edits were static HTML in a *different* repository, and the
block was un-fixable from inside the session without touching a protected guardrail file.
CI for that repo already runs unit (`test:coverage`) and e2e (`test:e2e`) as separate jobs;
`npm test` is a local convenience, not the contract.

## Decision Drivers

* A gate that cannot go green by any in-session action is a gate that gets bypassed or
  disabled; the promotion model (dryrun → enforce on measured FP) assumes gates are satisfiable
* Both enforcement points of one concern should run the same repo-declared command; the
  per-edit gate already trusts `preflight.toml`, the Stop gate should not silently disagree
* Autodetection stays as the fallback so repos without `preflight.toml` see no behavior change

## Considered Options

1. Vendored Stop script reads `preflight.toml [commands].test` and runs it in place of the
   autodetected command; falls back to autodetection when absent
2. Raise the Stop budget from 160 s to whatever the slowest repo needs
3. Change each affected repo's `npm test` to a unit-only script

## Decision Outcome

Option 1. The scoped command is the repo's declared contract for "the suite the gates run",
and the wrapper already documents it as such; making the runtime match the documentation is
the smallest change. Coverage ratchet behavior is unchanged: for a `package.json` repo the
script still reads `coverage/coverage-summary.json` if the scoped command produced one.

Rejected: option 2 only moves the cliff and leaves a Stop hook stalling for minutes; option 3
rewrites project scripts to satisfy tooling and has to be repeated per repo.

## Consequences

* Good: a repo can keep an honest, fast Stop gate (`personal-web-2025`: 837 vitest tests in
  ~7 s) while its e2e matrix stays in CI where it belongs
* Good: the two enforcement points of `test-gate` can no longer disagree on what "the suite" is
* Neutral: the vendored script gains a ~15-line minimal TOML section reader (no dependency);
  only `[commands] test = "..."` is parsed
* Risk: a repo can declare a trivially green scoped command. Accepted — the same is already
  true of the per-edit gate, and the commit-integrity gate covers the commit boundary
