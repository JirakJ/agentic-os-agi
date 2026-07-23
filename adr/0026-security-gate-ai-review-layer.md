---
status: accepted
date: 2026-07-23
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/security-gate, agent/security-scanner, agent/security-validator, command/security-review]
supersedes: []
superseded-by: []
---

# ADR-0026 — Security-gate AI review layer

## Context and Problem Statement

`core-guardrails` already runs a mechanical security gate: `PreToolUse/20_security_gate.py`
denies secret-path access and destructive Bash, and the commit-integrity path shells out to
gitleaks/semgrep/osv-scanner before a commit is allowed to land (ADR-0017, ADR-0022). That gate
is fast, deterministic and pattern-based — it catches a hardcoded key or an `rm -rf` before it
happens, but it cannot trace whether a request parameter reaches a SQL sink three files away,
whether an auth check is missing on one route but present on its neighbour, or whether a
"vulnerable" pattern is actually unreachable dead code. That is a reasoning problem, not a
pattern-matching one — the class of review Claude Security
(https://claude.com/product/claude-security) targets: contextual, data-flow-aware vulnerability
review with adversarial validation before anything is reported as real.

Naming makes this sharper than it looks: core-guardrails' internal hook is itself dispatched
under the name `security-gate` (ADR-0022's concern table lists it literally as
`hook/20_security_gate`). A new plugin also named `security-gate` must not become a second gate
runtime for that same concern — ADR-0022 is explicit that a gate firing twice on one concern
trains people to disable gates, and the marketplace only tolerates one runtime per concern.

## Decision Drivers

* Contextual/data-flow review needs a model reasoning over cross-file evidence, not a hook
  matching a request payload in isolation — hooks cannot do this at all
* ADR-0022 forbids a second hook-based runtime on the security concern core-guardrails already
  owns; anything shipped here that fires automatically would violate that decision on day one
* A model asked to find vulnerabilities over-reports by default; unvalidated findings training
  a human to skim security output is the same failure mode ADR-0022 names for gates
* Patching a real vulnerability is a code change with judgement calls (behaviour preservation,
  style, blast radius) that must stay human-gated, not auto-applied by an agent under deadline
  pressure to look useful

## Considered Options

* **Extend `core-guardrails`' hook with more patterns.** Cheapest to ship, but a hook cannot
  trace data flow across files or reason about reachability — it would only ever approximate
  what an LLM read-through already does better, and it keeps growing the one component ADR-0022
  already flagged as doing too much.
* **A skill that runs inline whenever security-sensitive code is touched.** Triggers unreliably
  (skills undertrigger by design) and, if it did trigger reliably, would behave like an
  undeclared gate — the same "fires without being asked" property ADR-0022 is trying to keep to
  one owner per concern.
* **A separate on-demand plugin, invoked deliberately, that ships no hooks.** Chosen.

## Decision Outcome

Ship `security-gate` as a new plugin whose only entry point is `/security-review` — a command the
human or an orchestrating agent invokes deliberately, never something that fires on its own. The
plugin ships **no hooks, no `mcpServers`, no `permissionMode`**, so it cannot become a second
runtime for the concern `core-guardrails` already owns; it is additive reasoning, not another gate.

The command runs three stages: **Scan** dispatches one `security-scanner` subagent per dimension
(injection, auth/access control, secrets & config exposure, unsafe memory/deserialization,
cross-file taint) in parallel, each returning structured findings with a data-flow trace, never a
fix. **Validate** sends every finding to a `security-validator` subagent briefed to actively
refute it by default (unreachable path, upstream sanitization, test-only code, framework
mitigation) — refuted findings are dropped silently, and an uncertain verdict defaults to
REFUTED rather than CONFIRMED, because a false positive that trains distrust costs more than a
missed finding that a human scan would have caught anyway. **Review & Patch** proposes a minimal
patch per CONFIRMED finding and stops: nothing is written to disk without an explicit per-patch
human approval.

### Consequences

Good: the marketplace gets contextual vulnerability review without adding a second runtime to
the concern ADR-0022 already resolved — `security-gate` and `core-guardrails`' `20_security_gate`
hook can be described in one sentence each without contradiction (deliberate reasoning vs.
always-on mechanical denial). Patch application stays a human decision, so a validator that is
wrong costs a rejected suggestion, never a silent bad edit.

Bad: because it ships no hooks, `/security-review` only runs when someone remembers to run it —
there is no automatic backstop if a session never invokes it. That is deliberate (an automatic
backstop is exactly the second-runtime shape ADR-0022 forbids), but it means this plugin's value
depends entirely on it being invoked, which is a discipline problem this ADR does not solve. If
that proves to be a real gap, the right fix is a `governance-gates` or `autonomic-loop` policy
that *reminds* a session to run `/security-review` before a risky commit — not a hook inside this
plugin that runs the review itself.
