---
status: accepted
date: 2026-07-19
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [script/skill-budget-lint]
supersedes: [0023]
superseded-by: []
---

# ADR-0024 — The listing budget measures the installed set, not the repository

## Context and Problem Statement

ADR-0023 accepted that the merged distribution overflows a 200k context's 1% skill-listing
budget (3383 tokens, 169%), kept the strict default, and added an explicit denominator. Its
own Consequences section named the real defect and deferred it:

> the lint currently globs `plugins/*/skills/*` and so charges you for plugins you never
> installed. That is the real bug; this record only makes the constraint honest until someone
> fixes the measurement.

This record fixes the measurement. A marketplace is not an install: this repo ships eleven
plugins precisely so that nobody has to take all of them (ADR-0002). Measuring the repository
therefore gated on a configuration that no runtime ever has.

## Decision Drivers

* The number a gate prints must describe something real, or people learn to discount it
* "Nothing installed" and "cannot tell what is installed" must not produce the same answer —
  a gate that passes because it could not find its input is not a gate
* CI has no install state and must still gate on something meaningful
* No new configuration file: the install state already exists and is authoritative

## Considered Options

* **Declare install profiles in the repo.** Invents a second source of truth that drifts from
  what is actually installed. Rejected.
* **Measure the repo, raise the ceiling.** What ADR-0023 refused to do, for the same reason.
* **Read Claude Code's installed-plugin state, fall back to the full distribution.** Chosen.

## Decision Outcome

`skill-budget-lint` resolves its scope in this order:

1. Read `~/.claude/plugins/installed_plugins.json` and select the plugins whose key ends in
   `@<this marketplace's name>`. Measure those. Scope prints as `installed set`.
2. If that file is unreadable, or names no plugin from this marketplace, measure every plugin
   in the repo. Scope prints as `full distribution`.

Case 2 is deliberately the worst case rather than zero. On a fresh clone or in CI the honest
answer to "how much will this cost you?" is "as much as taking all of it", and that is the
number the gate should defend against.

The `AGENTIC_OS_CONTEXT_TOKENS` denominator from ADR-0023 survives unchanged, as does the
conservative 200k default. The failure message now names all three real remedies — install
fewer plugins, trim descriptions, or raise the window if the runtime genuinely has it —
rather than only the two that were available before.

### Consequences

Good: the reported number describes a configuration that exists. A developer who installs
three plugins is measured on three plugins. The full-distribution figure remains reachable and
is what CI enforces.

Bad: the gate's result now depends on machine state, so two developers on the same commit can
legitimately see different numbers. The scope label in the output exists to make that visible
rather than confusing; a run whose scope reads `installed set` is not comparable to one that
reads `full distribution`, and neither is a regression in the other's terms.
