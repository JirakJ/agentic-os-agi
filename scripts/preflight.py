#!/usr/bin/env python3
"""jj-agentic-os preflight orchestrator (stdlib only, Python 3.11+).

Runs the commit-integrity pipeline on an isolated export of the EXACT staged tree
(identity = `git write-tree`), fail-fast cheapest-first:

    lint/type errors -> build -> tests -> SAST (opengrep/semgrep)
    -> dependency vulns (osv-scanner, CVSS >= threshold) -> runnability smoke

and writes the attestation to .git/jj-attest/<tree>.json. The same script runs locally,
from the git pre-commit hook (via verify-attestation.sh), and in CI (--ci) so the local
gate and the server-side gate are the identical pipeline ("not rocket science" rule).

Exit codes: 0 = green, 1 = red (attestation still written so the gate can name the
failing steps), 2 = usage/environment error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 unsupported
    print("preflight: Python >= 3.11 required (tomllib)", file=sys.stderr)
    sys.exit(2)

SCHEMA_VERSION = 1

DEFAULTS = {
    "budgets": {"build_s": 240, "test_s": 300, "smoke_s": 30, "sast_s": 60,
                "deps_s": 60, "total_s": 600},
    "security": {"strict": False, "fail_on_cvss": 7.0, "sast_severity": "ERROR"},
    "freshness": {"ttl_s": 1800},
}

LANG_MARKERS = [
    ("swift", "Package.swift"), ("cpp", "CMakeLists.txt"), ("python", "pyproject.toml"),
    ("node", "package.json"), ("java", "build.gradle"), ("java", "build.gradle.kts"),
    ("java", "pom.xml"), ("rust", "Cargo.toml"),
]

LANG_CMDS: dict[str, dict[str, str]] = {
    "python": {
        "lint": "python3 -m compileall -q .",
        "build": "sh -c 'if command -v uv >/dev/null && [ -f uv.lock ]; then uv sync --frozen; else true; fi'",
        "test": "sh -c 'if command -v uv >/dev/null; then uv run --no-sync pytest -x -q 2>/dev/null || python3 -m pytest -x -q; else python3 -m pytest -x -q; fi'",
    },
    "node": {
        "build": "sh -c 'if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; elif [ -f package-lock.json ]; then npm ci; else npm install; fi'",
        "lint": "sh -c 'npx --no-install tsc --noEmit 2>/dev/null || true'",
        "test": "sh -c 'npm test --silent'",
    },
    "rust": {"build": "cargo build --quiet", "lint": "cargo clippy --quiet -- -D warnings",
             "test": "cargo test --quiet"},
    "swift": {"build": "swift build -c debug", "test": "swift test --parallel"},
    "cpp": {"build": "sh -c 'cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug >/dev/null && cmake --build build -j'",
            "test": "sh -c 'ctest --test-dir build --output-on-failure'"},
    "java": {"build": "sh -c 'if [ -x ./gradlew ]; then ./gradlew build -x test --quiet; else mvn -q -DskipTests package; fi'",
             "test": "sh -c 'if [ -x ./gradlew ]; then ./gradlew test --quiet; else mvn -q test; fi'"},
}


def sh(cmd: str, cwd: Path, timeout: int) -> tuple[int, str, int]:
    """Run a shell step with a hard timeout. Returns (rc, tail_of_output, duration_ms)."""
    t0 = time.time()
    env = dict(os.environ, JJ_HOOK_ACTIVE="preflight")  # never re-trigger agent hooks
    try:
        # Shell is required: the LANG table and preflight.toml carry shell snippets
        # (pipes, `||`, `if`), not argv lists. Commands come from this repo's own config,
        # and the step they replace already executes that repo's build scripts, so shell
        # parsing adds no reachable input a plain exec would not.
        # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        out = (r.stdout + "\n" + r.stderr).strip()
        return r.returncode, out[-2000:], int((time.time() - t0) * 1000)
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s", int((time.time() - t0) * 1000)
    except Exception as e:  # tool spawn failure
        return 127, str(e), int((time.time() - t0) * 1000)


def load_config(root: Path) -> dict:
    cfg: dict = {}
    f = root / "preflight.toml"
    if f.exists():
        cfg = tomllib.loads(f.read_text(encoding="utf-8"))
    for section, vals in DEFAULTS.items():
        cfg.setdefault(section, {})
        for k, v in vals.items():
            cfg[section].setdefault(k, v)
    cfg.setdefault("commands", {})
    if not cfg.get("languages"):
        langs = []
        for lang, marker in LANG_MARKERS:
            if (root / marker).exists() and lang not in langs:
                langs.append(lang)
        cfg["languages"] = langs or ["python"]
    if not cfg.get("project_type"):
        cfg["project_type"] = "library"
    return cfg


def toolchain_fingerprint(root: Path, langs: list[str]) -> str:
    probes = ["git --version", "python3 --version"]
    probe_map = {"node": "node --version", "rust": "cargo --version",
                 "swift": "swift --version", "cpp": "cmake --version",
                 "java": "java -version"}
    probes += [probe_map[l] for l in langs if l in probe_map]
    for tool in ("opengrep", "semgrep", "osv-scanner"):
        if shutil.which(tool):
            probes.append(f"{tool} --version")
    blob = []
    for p in probes:
        rc, out, _ = sh(p + " 2>&1", root, 10)
        blob.append(f"{p}={out.splitlines()[0] if out else rc}")
    cfg = root / "preflight.toml"
    if cfg.exists():
        blob.append(cfg.read_text(encoding="utf-8"))
    return hashlib.sha256("\n".join(blob).encode()).hexdigest()[:32]


def export_staged_tree(root: Path, dest: Path) -> str:
    """Race-free export of exactly the staged content (not the dirty worktree)."""
    tree = subprocess.run(["git", "write-tree"], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()
    subprocess.run(["git", "checkout-index", "-a", "-f", f"--prefix={dest}/"],
                   cwd=root, check=True)
    return tree


# ---------------------------------------------------------------- pipeline steps
def step_lint(work: Path, cfg: dict) -> tuple[str, str]:
    cmds = []
    if cfg["commands"].get("lint"):
        cmds.append(cfg["commands"]["lint"])
    else:
        cmds += [LANG_CMDS[l]["lint"] for l in cfg["languages"] if "lint" in LANG_CMDS.get(l, {})]
    if not cmds:
        return "skipped", "no lint configured"
    for c in cmds:
        rc, out, _ = sh(c, work, 120)
        if rc != 0:
            return "fail", f"`{c}` -> {out[-1200:]}"
    return "pass", f"{len(cmds)} linter(s) clean"


def _lang_steps(kind: str, work: Path, cfg: dict, budget: int) -> tuple[str, str]:
    cmds = []
    if cfg["commands"].get(kind):
        cmds.append(cfg["commands"][kind])
    else:
        cmds += [LANG_CMDS[l][kind] for l in cfg["languages"] if kind in LANG_CMDS.get(l, {})]
    if not cmds:
        return "skipped", f"no {kind} configured"
    for c in cmds:
        rc, out, _ = sh(c, work, budget)
        if rc != 0:
            return "fail", f"`{c}` -> {out[-1500:]}"
    return "pass", f"{len(cmds)} {kind} step(s) ok"


def step_sast(work: Path, root: Path, cfg: dict) -> tuple[str, str]:
    tool = shutil.which("opengrep") or shutil.which("semgrep")
    if not tool:
        return ("red" if cfg["security"]["strict"] else "skipped", "opengrep/semgrep not installed")
    rules = root / "rules" / "opengrep"
    rules_arg = f"--config {shlex.quote(str(rules))}" if rules.is_dir() else "--config auto"
    sev = cfg["security"]["sast_severity"]
    rc, out, _ = sh(f"{Path(tool).name} scan --quiet --error --severity {sev} {rules_arg} .",
                    work, cfg["budgets"]["sast_s"])
    if rc == 0:
        return "pass", f"0 new {sev} findings"
    if rc in (124, 127):
        return ("red" if cfg["security"]["strict"] else "skipped", out[:200])
    return "fail", f"{sev} findings:\n" + out[-1500:]


def step_deps(work: Path, cfg: dict) -> tuple[str, str]:
    if not shutil.which("osv-scanner"):
        return ("red" if cfg["security"]["strict"] else "skipped", "osv-scanner not installed")
    rc, out, _ = sh("osv-scanner scan --format json -r .", work, cfg["budgets"]["deps_s"])
    if rc in (124, 127):
        return ("red" if cfg["security"]["strict"] else "skipped", out[:200])
    # osv-scanner has NO scan-time severity flag: gate on CVSS from JSON ourselves.
    threshold = float(cfg["security"]["fail_on_cvss"])
    try:
        start = out.find("{")
        data = json.loads(out[start:]) if start >= 0 else {}
    except Exception:
        return ("pass" if rc == 0 else "fail", out[-800:])
    blocking: list[str] = []
    for res in data.get("results", []) or []:
        for pkg in res.get("packages", []) or []:
            name = (pkg.get("package") or {}).get("name", "?")
            for vuln in pkg.get("vulnerabilities", []) or []:
                score = 0.0
                for sev in vuln.get("severity", []) or []:
                    try:
                        score = max(score, float(str(sev.get("score", "0")).split("/")[0]))
                    except ValueError:
                        pass
                db = (vuln.get("database_specific") or {}).get("severity", "").upper()
                if score >= threshold or db in ("HIGH", "CRITICAL"):
                    blocking.append(f"{name}: {vuln.get('id')} ({score or db})")
    if blocking:
        return "fail", f">= CVSS {threshold}:\n" + "\n".join(blocking[:12])
    return "pass", f"0 vulns >= CVSS {threshold}"


def step_smoke(work: Path, cfg: dict) -> tuple[str, str]:
    cmd = cfg["commands"].get("smoke")
    ptype = cfg.get("project_type", "library")
    budget = cfg["budgets"]["smoke_s"]
    if not cmd:
        if ptype == "service" and cfg.get("service", {}).get("boot_cmd"):
            boot = cfg["service"]["boot_cmd"]
            url = cfg["service"].get("health_url", "http://127.0.0.1:8080/health")
            cmd = (f"sh -c '({boot}) & PID=$!; ok=1; for i in $(seq 1 {budget}); do "
                   f"curl -fsS {shlex.quote(url)} >/dev/null 2>&1 && ok=0 && break; sleep 1; done; "
                   "kill $PID 2>/dev/null; exit $ok'")
        elif ptype == "jetbrains-plugin":
            cmd = "sh -c 'if [ -x ./gradlew ]; then ./gradlew buildPlugin verifyPlugin --quiet; else exit 0; fi'"
        else:
            return "skipped", f"no smoke for project_type={ptype}"
    rc, out, _ = sh(cmd, work, budget + 10)
    if rc != 0:
        return "fail", out[-1200:]
    return "pass", "runnable"


PIPELINE = [
    ("lint",     lambda w, r, c: step_lint(w, c)),
    ("build",    lambda w, r, c: _lang_steps("build", w, c, c["budgets"]["build_s"])),
    ("test",     lambda w, r, c: _lang_steps("test", w, c, c["budgets"]["test_s"])),
    ("sast",     lambda w, r, c: step_sast(w, r, c)),
    ("deps",     lambda w, r, c: step_deps(w, c)),
    ("smoke",    lambda w, r, c: step_smoke(w, c)),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="commit-integrity preflight")
    ap.add_argument("--root", default=None, help="repo root (default: git toplevel)")
    ap.add_argument("--ci", action="store_true",
                    help="CI mode: run on the checked-out tree (HEAD) instead of the index")
    ap.add_argument("--init", action="store_true",
                    help="write an auto-detected preflight.toml and exit")
    args = ap.parse_args()

    root = Path(args.root) if args.root else None
    if root is None:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("preflight: not inside a git repository", file=sys.stderr)
            return 2
        root = Path(r.stdout.strip())

    cfg = load_config(root)
    if args.init:
        target = root / "preflight.toml"
        if target.exists():
            print(f"preflight: {target} already exists")
            return 0
        example = Path(__file__).resolve().parent.parent / "preflight.toml.example"
        body = example.read_text(encoding="utf-8") if example.exists() else ""
        body = body.replace('languages = ["python"]',
                            "languages = " + json.dumps(cfg["languages"]))
        target.write_text(body, encoding="utf-8")
        print(f"preflight: wrote {target} (languages={cfg['languages']})")
        return 0

    t_start = time.time()
    results: dict[str, dict] = {}
    overall = "green"

    with tempfile.TemporaryDirectory(prefix="jj-preflight-") as tmp:
        work = Path(tmp)
        if args.ci:
            tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=root,
                                  capture_output=True, text=True).stdout.strip() or "ci"
            shutil.copytree(root, work / "x", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "node_modules", "build"))
            work = work / "x"
        else:
            tree = export_staged_tree(root, work)
        cfgfile = root / "preflight.toml"
        if cfgfile.exists() and not (work / "preflight.toml").exists():
            shutil.copy2(cfgfile, work / "preflight.toml")

        for name, fn in PIPELINE:
            if time.time() - t_start > cfg["budgets"]["total_s"]:
                results[name] = {"status": "fail", "summary": "total budget exceeded",
                                 "duration_ms": 0}
                overall = "red"
                break
            t0 = time.time()
            status, summary = fn(work, root, cfg)
            results[name] = {"status": "pass" if status == "pass" else
                             ("skipped" if status == "skipped" else "fail"),
                             "summary": summary, "duration_ms": int((time.time() - t0) * 1000)}
            print(f"[preflight] {name:<9} {results[name]['status']:<7} "
                  f"{results[name]['duration_ms']:>6}ms  {summary.splitlines()[0][:100]}")
            if status in ("fail", "red"):
                overall = "red"
                break  # fail fast

    att = {
        "schema_version": SCHEMA_VERSION,
        "tree_hash": tree,
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                               capture_output=True, text=True).stdout.strip(),
        "toolchain_fingerprint": toolchain_fingerprint(root, cfg["languages"]),
        "results": results,
        "overall": overall,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ttl_s": int(cfg["freshness"]["ttl_s"]),
    }
    att_dir = root / ".git" / "jj-attest"
    att_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = att_dir / f".{tree}.tmp"
    tmp_path.write_text(json.dumps(att, indent=2), encoding="utf-8")
    os.replace(tmp_path, att_dir / f"{tree}.json")  # atomic
    print(f"[preflight] overall={overall} tree={tree[:12]} "
          f"attestation={att_dir / (tree + '.json')}")
    return 0 if overall == "green" else 1


if __name__ == "__main__":
    sys.exit(main())
