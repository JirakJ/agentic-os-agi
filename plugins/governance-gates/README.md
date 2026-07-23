# governance-gates

Hook-enforced quality gates for the marketplace's own core logic (ADR-0005): a secret guard,
manifest/SemVer validation on every core write, atomic-commit and ADR enforcement at turn's end,
and an append-only audit trail of every tool call. Pure-Python hooks, stdlib only, no external
dependencies — a fresh clone runs the gates with no install step.

## Components

| Component | Event | Effect | Enforces |
|---|---|---|---|
| `hooks/scripts/secret_guard.py` | `PreToolUse` (Read\|Write\|Edit\|MultiEdit\|NotebookEdit\|Bash) | deny | content about to be written never contains a live credential shape (API keys, PATs, private key blocks, JWTs, …) |
| `hooks/scripts/core_change_tracker.py` | `PostToolUse` (Write\|Edit\|MultiEdit\|NotebookEdit) | records | which core components (`plugins/`, `adr/`) this session touched, into a per-session ledger |
| `hooks/scripts/manifest_validator.py` | `PostToolUse` (Write\|Edit\|MultiEdit\|NotebookEdit) | block | runs `doctor.py` scoped to what was just written — a component never stays broken past the edit that broke it |
| `hooks/scripts/audit_logger.py` | `PostToolUse` (`*`) | records | append-only, payload-free trail of every tool call — actions, never file contents or command output |
| `hooks/scripts/commit_adr_gate.py` | `Stop`, `SubagentStop` | block | dirty core logic (uncommitted skill/agent/hook/manifest) and behavioural changes with no ADR |
| `skills/governance-policy` | skill | — | explains what each gate blocks, why, and how to resolve a block correctly |
| `commands/os-audit.md` (`/os-audit`) | command | — | summarise a day's audit trail: tool counts, components touched, failed calls |

`hooks/scripts/_lib.py` is the shared runtime (stdin/stdout protocol, `plugin_data()`,
`marketplace_root()`, `classify()`/`component_id()`) every gate above imports — kept import-light
because hooks run synchronously on the critical path and stack.

Depends on `core-orchestration`: `manifest_validator.py` shells out to
`plugins/core-orchestration/scripts/doctor.py`.

## How this relates to `core-guardrails`

This plugin used to carry three secret-scanning layers — path, bash, and content. After the merge
that produced this repo, `core-guardrails` ships its own always-enforcing security gate covering
the same ground for the whole OS, and running two scanners over one input produced two denials for
one mistake and an override (`/gate-unlock`) that only half worked, because this plugin's gate never
honoured it. ADR-0022 resolves the overlap by splitting the concern rather than running both in
full:

| | `core-guardrails`' security gate | `governance-gates`' `secret_guard.py` (this plugin) |
|---|---|---|
| Path layer (`.env`, `id_rsa`, `.aws/credentials`, …) | owns it | removed |
| Bash layer (destructive commands, credential-shaped args) | owns it | removed |
| Content layer (a secret arriving via paste/API response about to be written to a file) | — | owns it |
| Override (`/gate-unlock`) | honoured | not applicable — this gate has no override, it only covers content |
| Telemetry | emits it | — |

What survives here is deliberately the layer the other gate does not have. If you are tuning
secret detection, decide which of the two plugins the change belongs in before writing it — adding
a fourth layer split across both is exactly the duplication ADR-0022 removed.

The rest of this plugin (`core_change_tracker`, `manifest_validator`, `commit_adr_gate`,
`audit_logger`) has no equivalent in `core-guardrails` — it is specific to this marketplace's own
component discipline (atomic commits, ADR enforcement, manifest validity), not general-purpose
security scanning.

## Usage

Nothing here is invoked directly except `/os-audit` — the rest is hooks that fire on every matching
tool call whether anyone asked for it or not. When one blocks:

- **`secret_guard`** denied a write — you do not need the literal value; reference the variable name
  and let the runtime resolve it, or ask the user to paste the one value you genuinely need.
  `.env.example` and friends are explicitly allowed.
- **`manifest_validator`** blocked a write — the block carries `doctor.py`'s findings; fix them in
  the same turn. Common causes: `skill.json` version drift from `metadata.version`, a component
  filed under `.claude-plugin/`, a dangling ADR reference, a hook script missing `+x`.
- **`commit_adr_gate`** blocked the turn — core logic is uncommitted, or a behavioural change has no
  decision record. The block prints the exact `git add`/`git commit` lines per component. Commit
  each component separately; `git add -A && git commit -m "wip"` satisfies the gate and destroys the
  thing it protects.

```
/os-audit [YYYY-MM-DD]
```

Reads `${CLAUDE_PLUGIN_DATA}/audit/<day>.jsonl` — one JSON object per line, actions only, never
payloads. A component touched many times across many sessions without a matching commit is a sign
the commit gate is being worked around.

Read the `governance-policy` skill for the full troubleshooting path, including what a gate does
and does not resolve, and how to add a new gate (ADR first, then the script, then wire it into
`hooks/hooks.json`).
