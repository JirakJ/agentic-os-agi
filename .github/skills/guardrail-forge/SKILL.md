---
name: guardrail-forge
description: Create, tune, and promote guardrail hooks using telemetry. Use whenever a gate misfires (false positive), the user wants a new rule enforced automatically, a gate feels too strict or too loose, or when deciding to promote a dry-run gate to enforce. Also use for the weekly guardrail review and whenever /gate-status shows an FP proxy over 2%.
license: MIT
metadata:
  version: "3.0.0"
---

# Guardrail Forge

Meta-skill: evolve the guardrail layer safely. Gates are code + config under
`plugins/core-guardrails/hooks/`; their modes live in `gates.json`
(env `JJ_GATE_<NAME>` > `~/.jj-agentic-os/gates.json` > plugin default).

## Lifecycle: observe -> dry-run -> enforce
1. New or changed detection logic ALWAYS starts in `dryrun` (advisory + telemetry only).
2. Collect at least 20 fire events over >= 1 week of real work.
3. Promotion gate: FP proxy = overrides / denies from `python3 scripts/rollup-telemetry.py`
   must be **< 2%**. At >= 2%, tune patterns (allowlist.json) and stay in dry-run.
4. Promote by editing `~/.jj-agentic-os/gates.json` (mode: "enforce") - NOT the plugin
   default. The plugin file is gate-protected; changing it requires /gate-unlock + an ADR.

## Adding a new gate (reproducible procedure)
1. Pick the event: PreToolUse (can deny), PostToolUse (can block-and-feed-back),
   SubagentStop (can block), SessionStart/End (observe/inject only).
2. Copy the closest existing hook in `hooks/scripts/<Event>/` as `NN_name.py`
   (numeric prefix = execution order). Use `lib.cc` for I/O, `lib.gates` for mode,
   `lib.telem.emit()` for every decision, `lib.allowlists` for patterns.
3. Fail-open for quality gates, fail-CLOSED only for safety gates (secrets, gate files).
4. Add config to `allowlist.json`; add the gate name to `gates.json` with `"dryrun"`.
5. Add fixtures in `tests/fixtures/`: at least one must-block and one must-allow JSON
   (`x-expect: deny|allow|block`). Run `bash scripts/hook-dryrun-harness.sh` - must PASS.
6. Add a pytest in `plugins/core-guardrails/tests/` for the decision function.
7. Run `bash scripts/preflight.sh`; commit via the normal gate. Document the gate's intent
   and FP budget in an ADR (`adr/`).

## Tuning a false positive
1. Reproduce: find the `gate_fired` record in the telemetry queue (JJ_VAULT_ROOT/70-telemetry).
2. Decide: pattern too broad (fix regex/glob in allowlist.json), missing exemption
   (add to *_exempt_paths), or legitimate block (educate, keep).
3. Add a regression fixture reproducing the FP as must-allow. Harness must pass.
4. Log the tuning in a `30-retros/` vault note - the weekly rollup tracks whether FP drops.

## Validation gates for this skill's own output
- `bash scripts/hook-dryrun-harness.sh` PASS, `python3 -m pytest` PASS,
  `bash scripts/preflight.sh` green, and the new gate appears in `/gate-status`.
