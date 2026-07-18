---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: []
supersedes: []
superseded-by: []
---

# ADR-0020 — Command runners keep `shell=True` and suppress the semgrep audit rule

## Context and problem statement

`semgrep --config=auto` reports `python.lang.security.audit.subprocess-shell-true` at two
call sites that run a project's own build/test commands:

- `scripts/preflight.py:78` — `sh()`, the generic step runner
- `plugins/core-guardrails/hooks/scripts/PostToolUse/10_test_gate.py:62` — the test gate

Both execute a command string sourced from the `LANG` table in `preflight.py` or from
`commands.*` in the target repository's `preflight.toml`. The rule is `security.audit`
class — it flags the construct for review, not a proven injection. Left unaddressed, the
finding fires on every security-gate run and trains everyone to ignore the gate output.

## Decision drivers

- The gate must stay credible: a permanently-red finding is the same as no finding.
- The configured commands are shell snippets by design (`|`, `||`, `if ... fi`, `sh -c '...'`).
- Suppression must be narrow and justified at the call site, never repo-wide.

## Considered options

1. **Rewrite to `shell=False` with argv lists.** Breaks every entry in the `LANG` table and
   in existing `preflight.toml` files; the shell metacharacters are load-bearing, not
   incidental. Would require inventing a mini command language to replace the shell.
2. **Repo-wide `.semgrepignore` or `--exclude`.** Hides the whole rule, including future
   call sites that would be genuinely unsafe. Rejected.
3. **Per-call-site `# nosemgrep` with a written justification.** Chosen.

## Decision outcome

Chosen option 3: annotate both call sites with
`# nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true`
plus a comment stating why the shell is required and why it adds no reachable input.

Threat model behind the acceptance: the input is the target repository's own configuration,
and the command it names (`npm test`, `cargo test`, `./gradlew test`, ...) already executes
that repository's code. An attacker who controls `preflight.toml` controls the test command
regardless of how it is spawned, so `shell=True` grants no capability that `shell=False`
would deny. The escalation only matters if the repo itself is untrusted — and running its
build in-process is out of scope for both tools.

### Consequences

Good: security gate returns to green, so a new ERROR finding is a real signal again.
Shell snippets in `preflight.toml` keep working across all supported languages.

Bad: the two call sites are now exempt from this rule permanently. If either ever starts
taking a command from an untrusted source — a remote config, a CLI argument, a hook payload
field — the suppression must be removed and the input re-examined. The comments name the
input source precisely so that change is visible in review.

Editing `10_test_gate.py` required a `/gate-unlock` override, logged as `gate_override`
telemetry on 2026-07-18.
