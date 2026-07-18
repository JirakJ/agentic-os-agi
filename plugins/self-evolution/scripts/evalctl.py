#!/usr/bin/env python3
"""Capability-eval harness with regression tracking.

Distinct from tests/ (ADR-0008): tests assert correctness at a point in time; evals track a
capability *trajectory* across changes and catch degradation. This is the verification substrate
that makes self-improvement safe — a self-authored capability is adopted only if the full suite
shows no regression against a baseline (ADR-0008, ADR-0010).

An eval is a spec with a deterministic verifier:

    {
      "id": "repo-health",
      "capability": "validation",
      "kind": "invariant | script | artifact",
      "description": "The marketplace validates clean.",
      "verifier": { "type": "exit_zero", "command": ["python3", "…/doctor.py", "--quiet"] },
      "weight": 1.0
    }

Verifier types:
  exit_zero  — run a command in the repo root; pass iff it exits 0. For invariants.
  script     — run a python verifier that prints one JSON line {"pass", "score", "detail"}.
               For capability tests that build temp state and assert against it.
  artifact   — run a script verifier against a produced file (--artifact PATH). For
               model-dependent capabilities whose output an agent must produce first.

Usage:
    evalctl.py                       # run the suite, score, compare to baseline
    evalctl.py --set-baseline        # snapshot current scores as the reference
    evalctl.py --json                # machine-readable scorecard
    evalctl.py --eval repo-health    # run one eval
    evalctl.py --history             # recent snapshots from the ledger
    evalctl.py --artifact PATH       # supply an artifact for artifact-kind evals

Exit code: 0 = no regression, 1 = a capability regressed below baseline (a revert signal),
2 = usage/spec error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REGRESSION_EPS = 1e-9  # a drop beyond floating noise counts as a regression


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("evalctl: not inside a marketplace (no .claude-plugin/marketplace.json)", file=sys.stderr)
    sys.exit(2)


def plugin_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))


def data_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(raw) if raw else Path.home() / ".claude" / "plugins" / "data" / "self-evolution"
    (base / "evolution").mkdir(parents=True, exist_ok=True)
    return base / "evolution"


@dataclass
class EvalResult:
    id: str
    capability: str
    passed: bool
    score: float
    detail: str
    duration_ms: float


@dataclass
class Scorecard:
    results: list[EvalResult] = field(default_factory=list)
    sha: str = ""
    ts: str = ""

    @property
    def aggregate(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(r.score for r in self.results) / len(self.results), 4)

    def by_capability(self) -> dict[str, float]:
        buckets: dict[str, list[float]] = {}
        for r in self.results:
            buckets.setdefault(r.capability, []).append(r.score)
        return {cap: round(sum(v) / len(v), 4) for cap, v in buckets.items()}

    def scores(self) -> dict[str, float]:
        return {r.id: r.score for r in self.results}


def load_specs(root: Path, only: str | None) -> list[dict]:
    eval_dir = plugin_root() / "evals"
    specs: list[dict] = []
    for path in sorted(eval_dir.glob("*.json")):
        if path.name in {"baseline.json"}:
            continue
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"evalctl: {path.name} is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(2)
        if not spec.get("id") or not spec.get("verifier"):
            print(f"evalctl: {path.name} missing id or verifier", file=sys.stderr)
            sys.exit(2)
        if only and spec["id"] != only:
            continue
        specs.append(spec)
    if only and not specs:
        print(f"evalctl: no eval with id '{only}'", file=sys.stderr)
        sys.exit(2)
    return specs


def resolve(token: str, root: Path) -> str:
    return token.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root())).replace("${REPO_ROOT}", str(root))


def run_verifier(spec: dict, root: Path, artifact: str | None) -> EvalResult:
    verifier = spec["verifier"]
    vtype = verifier.get("type")
    started = time.perf_counter()

    passed, score, detail = False, 0.0, ""
    try:
        if vtype == "exit_zero":
            command = [resolve(t, root) for t in verifier["command"]]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    timeout=verifier.get("timeout", 60))
            passed = result.returncode == 0
            score = 1.0 if passed else 0.0
            detail = "" if passed else (result.stderr or result.stdout).strip().splitlines()[-1:][0] if (result.stderr or result.stdout).strip() else f"exit {result.returncode}"

        elif vtype in ("script", "artifact"):
            script = resolve(verifier["script"], root)
            command = [sys.executable, script, *[resolve(a, root) for a in verifier.get("args", [])]]
            if vtype == "artifact":
                if not artifact:
                    return EvalResult(spec["id"], spec.get("capability", "?"), False, 0.0,
                                      "artifact-kind eval needs --artifact PATH (an agent must produce it first)",
                                      round((time.perf_counter() - started) * 1000, 1))
                command += ["--artifact", artifact]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    timeout=verifier.get("timeout", 60))
            payload = _last_json_line(result.stdout)
            if payload is None:
                passed, score = False, 0.0
                detail = (result.stderr.strip().splitlines()[-1:] or ["verifier printed no JSON result"])[0]
            else:
                passed = bool(payload.get("pass"))
                score = float(payload.get("score", 1.0 if passed else 0.0))
                detail = str(payload.get("detail", ""))
        else:
            detail = f"unknown verifier type '{vtype}'"
    except subprocess.TimeoutExpired:
        detail = "verifier timed out"
    except (OSError, subprocess.SubprocessError) as exc:
        detail = f"verifier failed to run: {exc}"

    return EvalResult(
        id=spec["id"],
        capability=spec.get("capability", "uncategorised"),
        passed=passed,
        score=max(0.0, min(1.0, score)),
        detail=detail,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )


def _last_json_line(text: str) -> dict | None:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def git_sha(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def run_suite(root: Path, only: str | None, artifact: str | None) -> Scorecard:
    card = Scorecard(sha=git_sha(root), ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    for spec in load_specs(root, only):
        card.results.append(run_verifier(spec, root, artifact))
    return card


def append_ledger(card: Scorecard) -> None:
    ledger = data_dir() / "ledger.jsonl"
    snapshot = {
        "ts": card.ts, "sha": card.sha, "aggregate": card.aggregate,
        "scores": card.scores(), "by_capability": card.by_capability(),
    }
    try:
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot) + "\n")
    except OSError:
        pass


def load_baseline(root: Path) -> dict | None:
    committed = plugin_root() / "evals" / "baseline.json"
    if committed.is_file():
        try:
            return json.loads(committed.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    ledger = data_dir() / "ledger.jsonl"
    if ledger.is_file():
        lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1])
    return None


def set_baseline(card: Scorecard) -> Path:
    committed = plugin_root() / "evals" / "baseline.json"
    committed.write_text(json.dumps({
        "ts": card.ts, "sha": card.sha, "aggregate": card.aggregate,
        "scores": card.scores(), "by_capability": card.by_capability(),
    }, indent=2) + "\n", encoding="utf-8")
    return committed


def regressions(card: Scorecard, baseline: dict) -> list[tuple[str, float, float]]:
    base_scores = baseline.get("scores", {})
    out: list[tuple[str, float, float]] = []
    for r in card.results:
        if r.id in base_scores and r.score < base_scores[r.id] - REGRESSION_EPS:
            out.append((r.id, base_scores[r.id], r.score))
    return out


def render(card: Scorecard, baseline: dict | None) -> None:
    print(f"\ncapability evals — {len(card.results)} at {card.sha}\n")
    base_scores = (baseline or {}).get("scores", {})
    for r in sorted(card.results, key=lambda x: (x.capability, x.id)):
        mark = "\033[32mPASS\033[0m" if r.passed else "\033[31mFAIL\033[0m"
        if not sys.stdout.isatty():
            mark = "PASS" if r.passed else "FAIL"
        delta = ""
        if r.id in base_scores:
            d = r.score - base_scores[r.id]
            if abs(d) > REGRESSION_EPS:
                arrow = "↑" if d > 0 else "↓"
                delta = f"  {arrow}{abs(d):.2f} vs baseline"
        line = f"  {mark}  {r.score:.2f}  {r.capability}/{r.id}{delta}"
        print(line)
        if r.detail and not r.passed:
            print(f"          {r.detail}")

    print(f"\n  aggregate {card.aggregate:.4f}", end="")
    if baseline:
        base_agg = baseline.get("aggregate", 0.0)
        d = card.aggregate - base_agg
        print(f"   (baseline {base_agg:.4f}, {'+' if d >= 0 else ''}{d:.4f})")
    else:
        print("   (no baseline — set one with --set-baseline)")

    if baseline:
        regs = regressions(card, baseline)
        if regs:
            print(f"\n  \033[31m{len(regs)} regression(s)\033[0m — a revert signal (ADR-0008):" if sys.stdout.isatty()
                  else f"\n  {len(regs)} regression(s) — a revert signal (ADR-0008):")
            for eid, was, now in regs:
                print(f"    {eid}: {was:.2f} → {now:.2f}")


def cmd_history() -> int:
    ledger = data_dir() / "ledger.jsonl"
    if not ledger.is_file():
        print("no eval history yet")
        return 0
    lines = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{'when':<20} {'sha':<10} {'aggregate':<10} evals")
    for snap in lines[-15:]:
        print(f"{snap['ts']:<20} {snap['sha']:<10} {snap['aggregate']:<10.4f} {len(snap.get('scores', {}))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run capability evals and track regression.")
    parser.add_argument("--eval", dest="only", help="run a single eval by id")
    parser.add_argument("--set-baseline", action="store_true", help="snapshot current scores as the committed baseline")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--artifact", help="artifact path for artifact-kind evals")
    parser.add_argument("--no-ledger", action="store_true", help="do not append this run to the ledger")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()

    if args.history:
        return cmd_history()

    card = run_suite(root, args.only, args.artifact)

    if args.set_baseline:
        path = set_baseline(card)
        print(f"baseline set: {path.relative_to(root)}  (aggregate {card.aggregate:.4f}, {len(card.results)} evals)")
        print("commit it as the reference point:  git add "
              f"{path.relative_to(root)} && git commit -m 'chore(self-evolution): set eval baseline'")
        return 0

    baseline = load_baseline(root)
    if not args.no_ledger and not args.only:
        append_ledger(card)

    if args.as_json:
        print(json.dumps({
            "sha": card.sha, "ts": card.ts, "aggregate": card.aggregate,
            "scores": card.scores(), "by_capability": card.by_capability(),
            "results": [{"id": r.id, "capability": r.capability, "pass": r.passed,
                         "score": r.score, "detail": r.detail} for r in card.results],
            "regressions": [{"id": e, "was": w, "now": n}
                            for e, w, n in (regressions(card, baseline) if baseline else [])],
        }, indent=2))
    else:
        render(card, baseline)

    if baseline and regressions(card, baseline):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
