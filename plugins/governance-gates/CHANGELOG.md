# Changelog

Derived from Conventional Commits by git-cliff. Do not edit by hand.

## 2.0.1 — 2026-07-23

### Documentation

- **governance-gates**: Add README

## 2.0.0 — 2026-07-19

### Features

- **governance-gates**: Add the audit-trail command
- **skill/governance-policy**: Document the gates and how to resolve blocks (ADR-0005)
- **governance-gates**: Wire the gates to hook events (ADR-0005)
- **hook/commit-adr-gate**: Enforce atomic commits and ADRs at Stop
- **hook/audit-logger**: Append a structured trail of tool calls
- **hook/core-change-tracker**: Record touched components per session (ADR-0005)
- **hook/manifest-validator**: Block invalid component writes
- **hook/secret-guard**: Block reading or writing credentials
- **governance-gates**: Add the hook runtime library

### Refactoring

- **governance-gates**: Apply the ADR-0022 gate deconfliction (ADR-0022)


