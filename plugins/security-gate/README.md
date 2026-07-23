# security-gate

On-demand AI security review, modeled on
[Claude Security](https://claude.com/product/claude-security): contextual, data-flow-aware
vulnerability review with adversarial validation of every finding and human-gated patching.
One command — `/security-review` — three stages: **Scan** (five `security-scanner` agents, one
per dimension, in parallel) → **Validate** (one `security-validator` per finding, briefed to
refute by default) → **Review & Patch** (a ranked report; patches are proposed, never applied,
until a human approves each one). See ADR-0026.

## How this relates to `core-guardrails`

`core-guardrails` already ships a security gate — a mechanical, always-on `PreToolUse` hook
(`20_security_gate.py`) plus the commit-integrity path's gitleaks/semgrep/osv-scanner sweep
(ADR-0017). That gate is fast and deterministic: it catches a hardcoded key, a destructive `rm
-rf`, or a known-vulnerable dependency by pattern, and it fires on every relevant tool call
whether anyone asked for it or not.

`security-gate` does the opposite kind of work, on purpose:

| | `core-guardrails` (mechanical) | `security-gate` (this plugin) |
|---|---|---|
| Trigger | every matching tool call, automatically | only `/security-review`, invoked deliberately |
| Method | pattern/regex match, one file at a time | a model reading across files, tracing data flow |
| Catches | secrets in paths/bash, destructive commands, known-CVE deps | missing auth checks, cross-file taint, logic-level exposure, reachability judgement calls a regex cannot make |
| False positives | rare, by design (patterns are narrow) | expected, which is why every finding is adversarially validated before it is reported |
| Ships | hooks (`PreToolUse`) | **no hooks** — reasoning only |
| Fix | you fix it yourself, the gate just denies | a proposed patch, presented for explicit per-finding human approval |

Both are needed. Neither is a substitute for the other, and per ADR-0022 (one gate runtime per
concern) this plugin does not add a second automatic runtime on top of the one `core-guardrails`
already owns — it ships zero hooks, zero `mcpServers`, zero `permissionMode`. It cannot fire on
its own; it only runs because someone ran `/security-review`.

## Usage

```
/security-review
```

Reviews the current branch's changes against its base — the common case: "did the commit I'm
about to make introduce anything".

```
/security-review src/api/orders/
```

Reviews a specific path, useful for a targeted read of an area that changed recently or that
handles something sensitive (auth, payments, file uploads).

```
/security-review --diff v1.2.0
```

Reviews everything since a tag or ref — useful before cutting a release.

### Reading the output

- A finding that never appears was refuted by the validator and dropped silently — that is the
  point of the adversarial pass, not a bug in the report.
- `PLAUSIBLE` findings carry what would need to be true to confirm them, not a patch — a patch
  for an unconfirmed vulnerability is a guess dressed up as a fix.
- **Nothing is ever auto-applied.** A patch is a proposed diff in the report; it becomes a real
  edit only after you name it explicitly.
- "0 findings survived validation out of N scanned" is a valid, complete result. A review that
  finds nothing is not a review that did nothing — check the N to tell the two apart.

## Components

- `commands/security-review.md` — the entry point and the only way this plugin does anything.
- `agents/security-scanner.md` — read-only, one dimension per dispatch (injection, auth/access
  control, secrets & config exposure, unsafe memory/deserialization, cross-file taint).
- `agents/security-validator.md` — adversarial verifier; refutes by default, defaults to
  `REFUTED` on genuine uncertainty rather than guessing `PLAUSIBLE`.

No `hooks/`, no `scripts/`, no `skills/`. Everything here is invoked, nothing here is triggered.
