# Changelog

Derived from Conventional Commits by git-cliff. Do not edit by hand.

## 4.0.1 — 2026-10-27

### Chores

- Remove gitleaks from every gate, template and instruction

### Fixes

- **core-guardrails**: Name the confidential vault boundary generically
- **hook/stop-gates**: Test-gate runs preflight.toml [commands].test before autodetecting (ADR-0029)

## 4.0.0 — 2026-07-23

### Documentation

- **core-guardrails**: Correct README version header to v4.0.0
- **skill/guardrail-forge**: Document Stop as a valid gate event (ADR-0027)

### Features

- **hook/stop-gates**: Bring Stop gates under the dispatcher (ADR-0027)

### Tests

- **hook/stop-gates**: Cover Stop dispatch, enforce block, dryrun advisory (ADR-0027)

## 3.0.1 — 2026-07-19

### Features

- **doctor,budget**: Manifest the carried skills and measure what is installed (ADR-0024, ADR-0025)
- Merge the jj-agentic-os lineage into one marketplace — **BREAKING** (ADR-0021, ADR-0022, ADR-0023)

### Refactoring

- **governance-gates**: Apply the ADR-0022 gate deconfliction (ADR-0022)


