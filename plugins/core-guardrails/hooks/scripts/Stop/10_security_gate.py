#!/usr/bin/env python3
"""security-gate (Stop): aggregate SAST (semgrep, ERROR-only) +
dependency audit (osv-scanner) over the working tree before the session is allowed to
stop. This is the Stop-level half of the concern PreToolUse/20_security_gate.py owns at
the per-tool-call layer (ADR-0022); both read the SAME "security-gate" key in gates.json,
which ships enforcing because this concern is safety-critical, not tunable by default.

Delegates the actual scan to the vendored vendor/security-gate.mjs (verbatim port of the
former machine-local ~/.claude/hooks/security-gate.mjs; see ADR-0027) via lib.nodegate,
which is what makes gates.json - not machine-local settings.json - the one place that
decides whether a finding blocks Stop or is merely reported."""
import pathlib
import sys

from lib import cc, nodegate

GATE = "security-gate"
VENDOR = pathlib.Path(__file__).resolve().parent / "vendor" / "security-gate.mjs"
TIMEOUT_S = 200  # semgrep + osv-scanner sequentially; must stay under
                  # dispatch.sh's Stop-event sub-hook timeout (see dispatch.sh SUBHOOK_TIMEOUT)

def main() -> None:
    nodegate.run(GATE, VENDOR, sys.stdin.read(), TIMEOUT_S)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
