#!/usr/bin/env python3
"""rollup-telemetry: weekly aggregation of the JSONL queue into a vault dashboard note.

Computes per-gate fire counts, deny/advisory split, override count, and the FP proxy
(overrides / denies) that drives the dry-run -> enforce promotion decision (target < 2%).
Run manually or from the jj-sync scheduler. Reads processed/ + live queue, never deletes."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


def vault_root() -> Path:
    v = os.environ.get("JJ_VAULT_ROOT", str(Path.home() / "jj-vault"))
    return Path(v)


def main() -> int:
    root = vault_root()
    q = root / "70-telemetry" / "queue"
    if not q.is_dir():
        print(f"rollup-telemetry: no queue at {q}", file=sys.stderr)
        return 1
    cutoff = time.time() - 7 * 86400
    fires: dict[str, Counter] = defaultdict(Counter)
    events: Counter = Counter()
    skills: Counter = Counter()
    for f in list(q.glob("*.jsonl")) + list((q / "processed").glob("*.jsonl")):
        try:
            if f.stat().st_mtime < cutoff:
                continue
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ev = rec.get("event", "")
                events[ev] += 1
                d = rec.get("detail", {})
                if ev in ("gate_fired", "commit_gate"):
                    fires[d.get("hook", "?")][d.get("decision") or d.get("result", "?")] += 1
                if ev == "gate_override":
                    fires[d.get("hook", "?")]["override"] += 1
                if ev == "skill_used":
                    skills[d.get("name", "?")] += 1
        except OSError:
            continue
    lines = ["---", "schema: 2", "type: telemetry-rollup",
             f"generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
             "window_days: 7", "---", "", "# Guardrail telemetry (7 days)", "",
             "| gate | denies/blocks | advisories | passes | overrides | FP proxy |",
             "|---|---|---|---|---|---|"]
    for gate, c in sorted(fires.items()):
        denies = c.get("deny", 0) + c.get("block", 0) + c.get("miss", 0) + \
                 c.get("red", 0) + c.get("stale", 0)
        fp = (c.get("override", 0) / denies * 100) if denies else 0.0
        verdict = "PROMOTE" if denies >= 20 and fp < 2 else ("tune" if fp >= 2 else "collect")
        lines.append(f"| {gate} | {denies} | {c.get('advisory', 0)} | {c.get('pass', 0)} "
                     f"| {c.get('override', 0)} | {fp:.1f}% {verdict} |")
    lines += ["", "## Skill usage",
              *[f"- {n}: {c}x" for n, c in skills.most_common(15)],
              "", f"Raw events: {dict(events)}"]
    out = root / "70-telemetry" / "telemetry.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rollup-telemetry: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
