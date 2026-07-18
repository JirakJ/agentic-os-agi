#!/usr/bin/env python3
"""skill-budget-lint: keep skill metadata within the runtime listing budget.

Every installed skill contributes name+description to the always-on listing (budget
~= skillListingBudgetFraction (1%) x context; heuristic 3.5 chars/token).
Fails when the distribution's skills alone consume > 90% of it.

The context window is the variable here, and it is a property of the runtime, not of this
repo: 1% of 200k is 2000 tokens, 1% of 1M is 10000. Default stays at the conservative 200k
so the gate keeps failing loudly on small-context runtimes. Override deliberately with
AGENTIC_OS_CONTEXT_TOKENS when you know what you are running on. See ADR-0023: the full
11-plugin install does not fit the 200k budget, and installing a subset is the intended
answer — the plugin is the unit of distribution (ADR-0002)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT = int(os.environ.get("AGENTIC_OS_CONTEXT_TOKENS", 200_000))
BUDGET = int(0.01 * CONTEXT)


def main() -> int:
    total = 0
    rows: list[tuple[str, int]] = []
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        text = skill.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        desc = m.group(1) if m else ""
        tokens = int((len(skill.parent.name) + len(desc)) / 3.5)
        total += tokens
        rows.append((skill.parent.name, tokens))
    for name, t in sorted(rows, key=lambda x: -x[1]):
        print(f"  {name:<26} ~{t:>4} tokens")
    pct = 100 * total / BUDGET
    print(f"skill-budget-lint: {total} tokens = {pct:.0f}% of {BUDGET}-token listing budget")
    if total > 0.9 * BUDGET:
        print("FAIL: over 90% - trim descriptions or split plugins.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
