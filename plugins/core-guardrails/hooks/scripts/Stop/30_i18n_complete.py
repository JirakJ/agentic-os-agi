#!/usr/bin/env python3
"""i18n-complete (Stop): walk the repo for Apple String Catalogs (.xcstrings) and fail on
any key that is untranslated, stale or empty in any locale before the session is allowed
to stop. This is the Stop-level, whole-tree half of the concern PostToolUse/20_i18n_complete.py
owns at the per-edit, JSON-locale layer (ADR-0022); both read the SAME "i18n-complete" key
in gates.json - ships dryrun by default, promote via the guardrail-forge lifecycle once
measured. (Only .xcstrings is checked at Stop; locales/*.json parity is checked at the
PostToolUse edit boundary instead - see the vendored script's collectTargets().)

Delegates to the vendored vendor/i18n-complete.mjs (verbatim port of the former
machine-local ~/.claude/hooks/i18n-complete.mjs; see ADR-0027) via lib.nodegate."""
import pathlib
import sys

from lib import cc, nodegate

GATE = "i18n-complete"
VENDOR = pathlib.Path(__file__).resolve().parent / "vendor" / "i18n-complete.mjs"
TIMEOUT_S = 30  # pure fs/JSON walk, no external tool

def main() -> None:
    nodegate.run(GATE, VENDOR, sys.stdin.read(), TIMEOUT_S)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
