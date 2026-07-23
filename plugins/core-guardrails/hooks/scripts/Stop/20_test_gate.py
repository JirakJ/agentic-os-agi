#!/usr/bin/env python3
"""test-gate (Stop): run the full suite (swift test / cargo test / npm test, whichever
the repo has) and enforce a coverage ratchet before the session is allowed to stop. This
is the Stop-level, full-suite half of the concern PostToolUse/10_test_gate.py owns at the
per-edit, scoped layer (ADR-0022); both read the SAME "test-gate" key in gates.json -
ships dryrun by default, promote via the guardrail-forge lifecycle once measured.

Delegates to the vendored vendor/test-gate.mjs (verbatim port of the former machine-local
~/.claude/hooks/test-gate.mjs; see ADR-0027) via lib.nodegate. A repo with none of
Package.swift/Cargo.toml/package.json is a no-op for the vendored script - not this
gate's concern."""
import pathlib
import sys

from lib import cc, nodegate

GATE = "test-gate"
VENDOR = pathlib.Path(__file__).resolve().parent / "vendor" / "test-gate.mjs"
TIMEOUT_S = 160  # full suite run; keep the marketplace's own repo on a scoped
                  # preflight.toml [commands].test if it needs longer than this

def main() -> None:
    nodegate.run(GATE, VENDOR, sys.stdin.read(), TIMEOUT_S)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
