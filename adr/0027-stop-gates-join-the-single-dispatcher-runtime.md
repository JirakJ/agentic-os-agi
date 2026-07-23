---
status: accepted
date: 2026-07-23
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/core-guardrails, hook/dispatch.sh, hook/Stop-security-gate, hook/Stop-test-gate, hook/Stop-i18n-complete, hook/gates.json]
supersedes: []
superseded-by: []
---

# ADR-0027 — Stop gates join the single dispatcher runtime

## Context and Problem Statement

`core-guardrails`' dispatcher (`hooks/hooks.json` + `hooks/scripts/dispatch.sh`) covers every hook
event ADR-0022 assigned it — PreToolUse, PostToolUse, SessionStart, SessionEnd, PreCompact,
SubagentStop — except `Stop`. The three gates that actually run at `Stop` (aggregate secret/SAST/
dependency scan, full test suite + coverage ratchet, whole-tree translation completeness) instead
ran as machine-local Node scripts wired directly in `~/.claude/settings.json`
(`~/.claude/hooks/security-gate.mjs`, `test-gate.mjs`, `i18n-complete.mjs`), reading no config from
the plugin at all.

`hooks/scripts/gates.json` already declared modes for exactly these three concerns —
`security-gate: enforce`, `test-gate: dryrun`, `i18n-complete: dryrun` — but nothing at `Stop`
consulted them. Flipping a mode in `gates.json` did nothing to the gate a session actually felt;
the real switch was which lines existed in a settings.json that is not installed, not versioned,
and not part of what `/plugin install core-guardrails` gives anyone else. This is precisely the
"two gates fire, trained by different config" failure ADR-0022 already named for the concern this
dispatcher owns — it had just re-appeared one hook event later, between the marketplace and a
machine instead of between two plugins.

## Decision Drivers

* ADR-0022's rule — one gate runtime per concern, one place its mode lives — is violated the moment
  any enforcement point for a concern the dispatcher already owns sits outside it
* A mode declared in `gates.json` that nothing reads is worse than no declaration: it reads as
  documentation of real behaviour and is not
* The three Stop scripts are real, working, already-tuned logic (gitleaks/semgrep/osv-scanner
  aggregation, coverage ratchet, `.xcstrings` completeness) — the fix is where they run and what
  reads their exit code, not a rewrite
* `dispatch.sh`'s per-sub-hook timeout (25s) was tuned for the existing fast, in-process pattern
  matches; an external scanner or a full test suite legitimately needs minutes, not seconds

## Considered Options

* **Leave the three scripts in `~/.claude/settings.json`, only fix `gates.json`'s wording.**
  Doesn't fix anything — the config a user edits and the config a script reads would still be two
  different files on two different trust boundaries (marketplace vs. machine-local).
* **Rewrite the scanning/testing/i18n logic natively in Python inside the dispatcher.** Throws away
  working, already-debugged tool integration (gitleaks/semgrep/osv-scanner invocation, Swift/Cargo/
  npm coverage extraction, `.xcstrings` variation-walking) to re-derive it from scratch, for no
  behavioural gain.
* **Port the scripts into the plugin verbatim, add a thin `gates.json`-aware Python wrapper per
  gate, and give `dispatch.sh` a `Stop`-specific timeout budget.** Chosen.

## Decision Outcome

Chosen option: port, don't rewrite. `hooks/scripts/Stop/vendor/{security-gate,test-gate,
i18n-complete}.mjs` are byte-identical copies of the former machine-local scripts (`gitleaks.toml`
travels with `security-gate.mjs` in the same directory, which the script already resolved via
`import.meta.dirname` — nothing to adapt). Three numbered wrappers (`Stop/10_security_gate.py`,
`20_test_gate.py`, `30_i18n_complete.py`) each delegate to a new shared helper, `lib/nodegate.py`,
which is what actually closes the loop: it reads the gate's mode from `lib.gates` (the same
`gates.json` keys these concerns already declared), invokes `node` on the vendored script with the
original Stop payload passed through unchanged (so the script's own `stop_hook_active` loop guard
still applies), and translates the exit code — `enforce` turns a non-zero exit into `sys.exit(2)`,
which `dispatch.sh`'s existing (previously unused) fail-closed branch turns into a real block;
`dryrun` turns the same failure into a `systemMessage` advisory and always exits 0; `off` skips
before `node` ever runs. A missing `node` binary or a timeout fails open, matching the dispatcher's
own "a broken hook must never break the session" rule.

`dispatch.sh` gets one small, event-scoped change: the previously hardcoded 25-second per-sub-hook
timeout becomes a `case "$EVENT"` lookup, 25s everywhere unchanged, 210s for `Stop`. `hooks.json`'s
`Stop` entry gets its own 640s ceiling (three sub-hooks at their individual worst case, plus
margin) — still one dispatcher, one mechanism, just a budget aware that this event's gates are not
the millisecond pattern matches the other events' are.

`security-gate`, `test-gate` and `i18n-complete` each now name one concern spanning two enforcement
points — a fast, per-edit check (`PreToolUse`/`PostToolUse`) and a full, whole-tree check
(`Stop`) — and `gates.json` is the only place either point reads its mode from.
`~/.claude/settings.json`'s `Stop` hooks and the four files under `~/.claude/hooks/` this ADR
copied from are deprecated; removing them is a machine-local step outside this repo, done after
this change is verified.

### Consequences

* Good, because a mode flip in `gates.json` now genuinely changes what a session feels at every
  point that concern is checked, closing the exact gap ADR-0022 exists to prevent
* Good, because the working scanning/testing/i18n logic is preserved verbatim — nothing about
  *what* gets checked changed, only *where* it runs and *what governs whether it blocks*
* Bad, because a Stop-level full test suite or full security scan is inherently slower than
  anything else in this dispatcher; a monorepo whose suite exceeds ~150s should scope
  `preflight.toml`'s `[commands].test` rather than lean on this backstop for full-suite depth
* Bad, because the machine-local scripts this ADR ports from are not deleted by this change —
  until `~/.claude/settings.json` is edited by hand, both the old and new gates fire together
  (redundant, not conflicting: same logic, same findings), which is the intended transition state,
  not the end state

## More Information

Implemented in the `feat(hook/stop-gates)` and `refactor(hook/dispatch)` commits that accompany
this record; `plugins/core-guardrails` releases 3.1.0 in the same turn. Revisit if a repo's Stop
suite genuinely needs the full test-gate.mjs 600s ceiling this port narrowed to ~150s.
