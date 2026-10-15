---
description: Run a contextual, data-flow-aware AI security review over a path, a diff, or the current branch's changes — scan in parallel, adversarially validate every finding, then propose human-gated patches
argument-hint: "[<path> | --diff <ref> | (default: current branch's changes against its base)]"
---

Run the four-pillar review Claude Security's model is built on — contextual analysis, adversarial
validation, patch generation, human-gated approval — over `$ARGUMENTS`. This is reasoning, not
another mechanical gate: it complements the always-on `core-guardrails` Stop-hook scanner
(semgrep/osv-scanner), which catches what a regex can see in one file, with what only a
model reading across files can catch — missing auth checks, taint that crosses file boundaries,
"vulnerable-looking" code that is actually unreachable. `security-gate` ships no hooks and never
fires on its own (ADR-0026); it runs only because this command was invoked.

## 1. Resolve the target

- A path given as `$ARGUMENTS` — review everything under it.
- `--diff <ref>` — review `git diff <ref>...HEAD`.
- Nothing given — review the current branch's changes: `git diff $(git merge-base HEAD
  origin/main)...HEAD` (fall back to `main`/`master` if `origin/main` does not resolve). If that is
  empty (nothing committed yet, or on the base branch itself), say so and stop — there is nothing
  to review, and reviewing the whole tree "just in case" is not what was asked.

Read enough of the surrounding files that a scanner is reasoning over real code, not a diff hunk
stripped of context.

## 2. Scan — dispatch one `security-scanner` per dimension, in parallel

Launch five `security-scanner` subagents in the same turn (parallel `Task` calls, not sequential),
each given the same target and exactly one dimension:

```
Task(subagent_type="security-scanner", prompt="Target: <target>. Dimension: injection flaws. ...")
Task(subagent_type="security-scanner", prompt="Target: <target>. Dimension: auth bypass / access control. ...")
Task(subagent_type="security-scanner", prompt="Target: <target>. Dimension: secrets & config exposure. ...")
Task(subagent_type="security-scanner", prompt="Target: <target>. Dimension: unsafe memory / deserialization. ...")
Task(subagent_type="security-scanner", prompt="Target: <target>. Dimension: cross-file data-flow (taint). ...")
```

Each returns zero or more findings with file:line, severity, a data-flow trace where relevant, and
its own confidence — never a fix. Collect all of them before moving on; do not validate as they
trickle in, since a scanner's silence on "no findings" is itself information worth having in full
before ranking anything.

## 3. Validate — every finding, adversarially, one at a time

For each finding the scanners returned, dispatch a `security-validator` with the finding, its
trace, and the file(s) it names:

```
Task(subagent_type="security-validator", prompt="Verify this finding: <finding block>")
```

The validator's brief is to refute by default (unreachable path, sanitized upstream, test-only
code, a framework mitigation) and returns CONFIRMED, PLAUSIBLE, or REFUTED with a one-line
justification. **Drop every REFUTED finding silently** — do not list it, do not mention it in the
summary beyond the count. A refuted finding surviving into the report is exactly the noise this
adversarial pass exists to remove.

## 4. Review & Patch — propose, never apply

For every finding still standing (CONFIRMED and PLAUSIBLE), build the report:

- **Table**, ranked by severity descending (critical, high, medium, low), then by verdict
  (CONFIRMED before PLAUSIBLE):

  | Severity | Verdict | Location | Dimension | Summary |
  |---|---|---|---|---|
  | critical | CONFIRMED | `src/api/orders.ts:142` | injection | unparameterized query built from `req.query.sort` |

- **Per-finding detail** below the table: the full data-flow trace, the validator's justification,
  and — **for CONFIRMED findings only** — a minimal patch proposal that fixes the flaw without
  restructuring the surrounding code or changing its style. Present the patch as a diff to review;
  do **not** run `Edit`/`Write` against the file. For PLAUSIBLE findings, state what would need to
  be confirmed (the thing the validator could not verify by reading) instead of a patch — proposing
  a fix for an unconfirmed vulnerability guesses at a problem that might not exist.

- **Wait for explicit human approval, per patch, before applying anything.** Approving one patch is
  not approval for the rest — apply exactly the ones the human names, one at a time, and re-read
  the file afterward to confirm the patch landed cleanly.

If every finding was refuted (or the scanners returned none), say exactly that: **"0 findings
survived validation out of N scanned"** — with the N so "nothing to report" is distinguishable from
"nothing was checked". A clean result is a valid, useful outcome, not a failure to find something.
