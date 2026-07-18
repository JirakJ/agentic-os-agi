#!/usr/bin/env python3
"""Experience miner: turn the audit trail into ranked improvement signals.

The audit-logger hook (governance-gates) writes an append-only trail of every tool call — actions,
components, success flags, never payloads (ADR-0006, ADR-0009). This mines that trail plus git
history for three signal classes:

  workflow  — a tool n-gram recurring across sessions → candidate compound skill or command
  failure   — a tool failing repeatedly on the same target → candidate fix or guard
  co-edit   — components repeatedly edited together → candidate compound capability or coupling

Signals are pointers, not implementations: the trail records that Edit touched a component, not
what the edit was (ADR-0009). Each signal carries its evidence — how many sessions, how often — so
the proposal engine can rank and a human can judge (ADR-0010).

The trail lives in governance-gates' data dir. This resolves it in order: --audit-dir,
$AGENTIC_OS_AUDIT_DIR, a sibling of $CLAUDE_PLUGIN_DATA named governance-gates, then the home
fallback.

Usage:
    mine.py                          # human-readable signals
    mine.py --json                   # machine-readable, for propose.py
    mine.py --min-support 3          # a signal must recur in ≥ N sessions (default 3)
    mine.py --audit-dir PATH         # explicit trail location
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Tools whose sequencing carries workflow signal. Read-only navigation tools are excluded from
# n-grams — "Grep then Read" is how everything works and is not a capability gap.
WORKFLOW_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "Task"}
NGRAM_MIN, NGRAM_MAX = 2, 4


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("mine: not inside a marketplace", file=sys.stderr)
    sys.exit(2)


def resolve_audit_dir(explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("AGENTIC_OS_AUDIT_DIR"):
        candidates.append(Path(os.environ["AGENTIC_OS_AUDIT_DIR"]).expanduser())
    if os.environ.get("CLAUDE_PLUGIN_DATA"):
        # sibling plugin data dir: .../data/self-evolution → .../data/governance-gates/audit
        data = Path(os.environ["CLAUDE_PLUGIN_DATA"])
        candidates.append(data.parent / "governance-gates" / "audit")
        candidates.append(data / "audit")
    candidates.append(Path.home() / ".claude" / "plugins" / "data" / "governance-gates" / "audit")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


@dataclass
class Session:
    id: str
    tools: list[str] = field(default_factory=list)          # ordered
    edited: list[str] = field(default_factory=list)         # components/files edited
    failures: list[tuple[str, str]] = field(default_factory=list)  # (tool, target)


def load_sessions(audit_dir: Path) -> list[Session]:
    events: list[dict] = []
    for path in sorted(audit_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    events.sort(key=lambda e: e.get("ts", ""))

    grouped: dict[str, Session] = {}
    for event in events:
        sid = event.get("session") or "unknown"
        session = grouped.setdefault(sid, Session(id=sid))
        tool = event.get("tool", "")
        if tool:
            session.tools.append(tool)
        target = None
        if event.get("components"):
            target = event["components"][0]
        elif event.get("files"):
            target = event["files"][0]
        if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"} and target:
            session.edited.append(target)
        if event.get("ok") is False:
            session.failures.append((tool, target or event.get("summary", "")[:40] or "?"))
    return list(grouped.values())


def mine_workflows(sessions: list[Session], min_support: int) -> list[dict]:
    # session support: how many distinct sessions contain the n-gram at least once
    support: dict[tuple[str, ...], set[str]] = defaultdict(set)
    total_count: Counter[tuple[str, ...]] = Counter()
    for session in sessions:
        seq = [t for t in session.tools if t in WORKFLOW_TOOLS]
        seen_here: set[tuple[str, ...]] = set()
        for n in range(NGRAM_MIN, NGRAM_MAX + 1):
            for i in range(len(seq) - n + 1):
                gram = tuple(seq[i:i + n])
                if len(set(gram)) == 1:  # a single tool repeated is not a workflow
                    continue
                support[gram].add(session.id)
                total_count[gram] += 1
                seen_here.add(gram)

    signals = []
    for gram, sessions_with in support.items():
        if len(sessions_with) < min_support:
            continue
        # prefer longer, more-supported grams; drop a gram fully contained in a stronger longer one
        signals.append({
            "type": "workflow",
            "pattern": list(gram),
            "sessions": len(sessions_with),
            "occurrences": total_count[gram],
            "support": round(len(sessions_with) / max(len(sessions), 1), 3),
            "suggests": "compound skill or slash command that performs this sequence in one step",
        })
    signals = _dedupe_subsequences(signals)
    return sorted(signals, key=lambda s: (s["sessions"], len(s["pattern"]), s["occurrences"]), reverse=True)


def _dedupe_subsequences(signals: list[dict]) -> list[dict]:
    """Drop a workflow whose pattern is a contiguous subsequence of a longer one with equal or
    greater session support — the longer pattern already captures it."""
    kept = []
    patterns = sorted(signals, key=lambda s: len(s["pattern"]), reverse=True)
    for sig in signals:
        p = sig["pattern"]
        covered = False
        for other in patterns:
            op = other["pattern"]
            if len(op) <= len(p):
                continue
            if other["sessions"] < sig["sessions"]:
                continue
            if any(op[i:i + len(p)] == p for i in range(len(op) - len(p) + 1)):
                covered = True
                break
        if not covered:
            kept.append(sig)
    return kept


def mine_failures(sessions: list[Session], min_support: int) -> list[dict]:
    counts: Counter[tuple[str, str]] = Counter()
    session_support: dict[tuple[str, str], set[str]] = defaultdict(set)
    for session in sessions:
        for tool, target in session.failures:
            key = (tool, target)
            counts[key] += 1
            session_support[key].add(session.id)

    signals = []
    for (tool, target), n in counts.items():
        sessions_with = len(session_support[(tool, target)])
        if n < max(2, min_support - 1):
            continue
        signals.append({
            "type": "failure",
            "tool": tool,
            "target": target,
            "occurrences": n,
            "sessions": sessions_with,
            "suggests": "a fix, a guard, or a skill that handles this failure mode",
        })
    return sorted(signals, key=lambda s: (s["occurrences"], s["sessions"]), reverse=True)


def mine_coedits(sessions: list[Session], min_support: int) -> list[dict]:
    pair_support: dict[tuple[str, str], set[str]] = defaultdict(set)
    for session in sessions:
        unique = sorted(set(session.edited))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                pair_support[(unique[i], unique[j])].add(session.id)

    signals = []
    for (a, b), sessions_with in pair_support.items():
        if len(sessions_with) < min_support:
            continue
        signals.append({
            "type": "co-edit",
            "components": [a, b],
            "sessions": len(sessions_with),
            "support": round(len(sessions_with) / max(len(sessions), 1), 3),
            "suggests": "a compound capability spanning both, or a documented coupling",
        })
    return sorted(signals, key=lambda s: s["sessions"], reverse=True)


def git_churn(root: Path) -> list[dict]:
    """Components changed most often in git history — high-activity areas that may warrant tooling."""
    try:
        out = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "--", "plugins/"],
            cwd=root, capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    counts: Counter[str] = Counter()
    for line in out.splitlines():
        line = line.strip()
        if "/skills/" in line and line.endswith("SKILL.md"):
            parts = line.split("/")
            counts[f"skill/{parts[parts.index('skills') + 1]}"] += 1
        elif "/agents/" in line and line.endswith(".md"):
            counts[f"agent/{Path(line).stem}"] += 1
    return [{"component": c, "changes": n} for c, n in counts.most_common(5) if n >= 2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine the audit trail for improvement signals.")
    parser.add_argument("--audit-dir", help="trail location (default: auto-resolve)")
    parser.add_argument("--min-support", type=int, default=3, help="minimum sessions for a signal")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()
    audit_dir = resolve_audit_dir(args.audit_dir)

    sessions: list[Session] = []
    if audit_dir:
        sessions = load_sessions(audit_dir)

    signals = {
        "workflows": mine_workflows(sessions, args.min_support),
        "failures": mine_failures(sessions, args.min_support),
        "co_edits": mine_coedits(sessions, args.min_support),
        "churn": git_churn(root),
    }
    meta = {
        "audit_dir": str(audit_dir) if audit_dir else None,
        "sessions_analysed": len(sessions),
        "min_support": args.min_support,
    }

    if args.as_json:
        print(json.dumps({"meta": meta, "signals": signals}, indent=2))
        return 0

    if not audit_dir:
        print("mine: no audit trail found. The trail accrues as the fleet runs under "
              "governance-gates; there is nothing to mine on a fresh install (ADR-0009).")
        return 0

    print(f"\nmined {len(sessions)} session(s) from {audit_dir}\n")
    total = sum(len(v) for v in signals.values())
    if total == 0:
        print(f"  no signals at min-support {args.min_support}. Either usage is still light, or "
              "no pattern recurs often enough yet. Self-improvement has a cold start (ADR-0009).")
        return 0

    if signals["workflows"]:
        print("workflows — recurring tool sequences (candidate compound capabilities):")
        for s in signals["workflows"][:8]:
            print(f"  {' → '.join(s['pattern'])}   {s['sessions']} sessions, {s['occurrences']}×")
    if signals["failures"]:
        print("\nfailures — recurring failure modes (candidate fixes or guards):")
        for s in signals["failures"][:8]:
            print(f"  {s['tool']} on {s['target']}   {s['occurrences']}× across {s['sessions']} sessions")
    if signals["co_edits"]:
        print("\nco-edits — components changed together (candidate compound capability or coupling):")
        for s in signals["co_edits"][:8]:
            print(f"  {s['components'][0]}  +  {s['components'][1]}   {s['sessions']} sessions")
    if signals["churn"]:
        print("\nchurn — most-changed components (high-activity areas):")
        for s in signals["churn"]:
            print(f"  {s['component']}   {s['changes']} changes")

    print(f"\n{total} signal(s). Turn them into proposals:  propose.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
