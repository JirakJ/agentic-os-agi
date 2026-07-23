# Changelog

Derived from Conventional Commits by git-cliff. Do not edit by hand.

## 0.1.0 — 2026-07-23

### Features

- **security-gate**: Add the on-demand AI security review layer (ADR-0026) — `/security-review`
  runs contextual, data-flow-aware scanning across five dimensions in parallel, adversarially
  validates every finding, and proposes human-gated patches. Ships no hooks; complements
  `core-guardrails`' mechanical gitleaks/semgrep/osv-scanner Stop-hook gate rather than
  duplicating it (ADR-0022).
