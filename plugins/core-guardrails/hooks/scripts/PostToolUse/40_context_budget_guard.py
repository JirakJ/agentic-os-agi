#!/usr/bin/env python3
"""context-budget-guard (PostToolUse leg): after Skill/Task use, opportunistically re-check
the skill-listing budget once per session and warn if > 90%. Heavy scan runs once."""
import json
import pathlib
import time

from lib import cc, gates, telem

GATE = "context-budget-guard"
BUDGET_TOKENS = int(0.01 * 200_000)  # skillListingBudgetFraction default 1% of 200k

def _est_tokens(chars: int) -> int:
    return int(chars / 3.5)

def _scan() -> tuple[int, list[tuple[str, int]]]:
    roots = [pathlib.Path.home() / ".claude" / "skills", pathlib.Path(".claude/skills"),
             pathlib.Path(".github/skills")]
    total = 0
    per: list[tuple[str, int]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for sk in root.glob("*/SKILL.md"):
            try:
                head = sk.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            desc = ""
            if head.startswith("---"):
                for line in head.splitlines()[1:]:
                    if line.strip() == "---":
                        break
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1]
            t = _est_tokens(len(sk.parent.name) + len(desc))
            total += t
            per.append((str(sk.parent.name), t))
    return total, sorted(per, key=lambda x: -x[1])

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") not in ("Skill", "Task") or not gates.active(GATE):
        cc.allow()
    sid = data.get("session_id", "")
    once = cc.home_dir() / f"budget-{sid[:24]}"
    if once.exists():
        cc.allow()
    try:
        once.write_text(str(time.time()))
    except OSError:
        pass
    total, per = _scan()
    if total <= 0.9 * BUDGET_TOKENS:
        cc.allow()
    top = ", ".join(f"{n} (~{t}t)" for n, t in per[:5])
    telem.emit("gate_fired", sid, hook=GATE, decision="advisory",
               est_tokens=total, budget=BUDGET_TOKENS)
    cc.system_message(
        f"context-budget-guard: skill descriptions ~{total} tokens = "
        f"{int(100 * total / BUDGET_TOKENS)}% of the listing budget ({BUDGET_TOKENS}t). "
        f"Longest: {top}. Trim descriptions or disable stale skills before the runtime "
        "silently drops long-tail skills.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
