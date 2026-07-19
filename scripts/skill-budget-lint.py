#!/usr/bin/env python3
"""skill-budget-lint: keep skill metadata within the runtime listing budget.

Every *installed* skill contributes name+description to the always-on listing (budget
~= skillListingBudgetFraction (1%) x context; heuristic 3.5 chars/token).

Two things vary, and ADR-0024 makes both explicit instead of hardcoding them:

  what is installed — a marketplace is not an install. Charging this repo for all eleven
      plugins measured a configuration nobody runs. When Claude Code's installed-plugin
      state is readable, the gate measures the plugins actually installed from this
      marketplace; otherwise (CI, a fresh clone) it measures the full distribution, which
      is the correct worst case there.

  the context window — a property of the runtime, not of this repo: 1% of 200k is 2000
      tokens, 1% of 1M is 10000. Default stays at a conservative 200k so the gate fails
      loudly on small-context runtimes; override with AGENTIC_OS_CONTEXT_TOKENS.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT = int(os.environ.get("AGENTIC_OS_CONTEXT_TOKENS", 200_000))
BUDGET = int(0.01 * CONTEXT)
STATE = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def marketplace_name() -> str:
    try:
        return json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())["name"]
    except (OSError, json.JSONDecodeError, KeyError):
        return ""


def installed_plugins() -> set[str] | None:
    """Plugins installed from this marketplace, or None when that is unknowable.

    None is not "nothing installed" — it means measure the worst case instead of silently
    reporting zero. A gate that passes because it could not find its input is not a gate.
    """
    market = marketplace_name()
    if not market or not STATE.is_file():
        return None
    try:
        data = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    names = {
        key.split("@", 1)[0]
        for key in (data.get("plugins") or {})
        if key.endswith(f"@{market}")
    }
    return names or None


def main() -> int:
    selected = installed_plugins()
    scope = "installed set" if selected is not None else "full distribution"

    total = 0
    rows: list[tuple[str, int]] = []
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        plugin = skill.parents[2].name
        if selected is not None and plugin not in selected:
            continue
        text = skill.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        desc = m.group(1) if m else ""
        tokens = int((len(skill.parent.name) + len(desc)) / 3.5)
        total += tokens
        rows.append((skill.parent.name, tokens))

    for name, t in sorted(rows, key=lambda x: -x[1]):
        print(f"  {name:<26} ~{t:>4} tokens")
    pct = 100 * total / BUDGET
    print(f"skill-budget-lint: {total} tokens = {pct:.0f}% of {BUDGET}-token listing budget "
          f"({scope}, {len(rows)} skills)")
    if total > 0.9 * BUDGET:
        print("FAIL: over 90% - install fewer plugins, trim descriptions, or raise "
              "AGENTIC_OS_CONTEXT_TOKENS if the runtime genuinely has the window.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
