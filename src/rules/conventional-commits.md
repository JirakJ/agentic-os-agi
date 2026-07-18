---
applyTo: "**"
description: "Commit and release conventions"
copilot_repo_wide: true
---
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`;
  `!`/`BREAKING CHANGE:` for majors. Imperative mood, English.
- SemVer per plugin (ADR-0002): the plugin is the unit of versioning and rollback. Bump the
  owning `plugin.json` and pin `ref` + `sha` for that plugin in marketplace.json. One component
  per commit (ADR-0004) — do NOT lockstep-bump every plugin for one plugin's change.
  Never leave finished work untagged.
- Commit only via a green preflight attestation (scripts/preflight.sh). Never use
  `--no-verify` to skip quality gates.
