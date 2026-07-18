"""End-to-end tests for the commit-integrity gate against a real git repo + attestations."""
import json
import os
import pathlib
import subprocess
import sys
import time

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "scripts"
HOOK = HOOKS / "PreToolUse" / "30_commit_integrity.py"


def make_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def run_gate(repo: pathlib.Path, tmp_path: pathlib.Path, mode: str = "enforce") -> str:
    env = dict(os.environ, PYTHONPATH=str(HOOKS), JJ_HOME=str(tmp_path / "state"),
               JJ_GATE_COMMIT_INTEGRITY=mode, JJ_VAULT_ROOT=str(tmp_path / "novault"))
    env.pop("JJ_HOOK_ACTIVE", None)
    payload = {"tool_name": "Bash", "session_id": "ci-test", "cwd": str(repo),
               "tool_input": {"command": "git commit -m 'feat: x'"}}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    assert r.returncode == 0, r.stderr
    return r.stdout


def write_att(repo: pathlib.Path, overall: str, age_s: int = 0) -> None:
    tree = subprocess.run(["git", "write-tree"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    d = repo / ".git" / "jj-attest"
    d.mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_s))
    (d / f"{tree}.json").write_text(json.dumps({
        "schema_version": 1, "tree_hash": tree, "head": "h",
        "toolchain_fingerprint": "f", "overall": overall,
        "results": {"test": {"status": "pass" if overall == "green" else "fail",
                             "summary": "s", "duration_ms": 1}},
        "ts": ts, "ttl_s": 1800}))


def test_denies_without_attestation(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    out = run_gate(repo, tmp_path)
    assert '"permissionDecision": "deny"' in out and "no build/test attestation" in out


def test_allows_with_green_attestation(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    write_att(repo, "green")
    out = run_gate(repo, tmp_path)
    assert out.strip() == ""


def test_denies_red_attestation(tmp_path):
    repo = make_repo(tmp_path)
    write_att(repo, "red")
    out = run_gate(repo, tmp_path)
    assert '"permissionDecision": "deny"' in out and "RED" in out


def test_denies_stale_attestation(tmp_path):
    repo = make_repo(tmp_path)
    write_att(repo, "green", age_s=4000)
    out = run_gate(repo, tmp_path)
    assert '"permissionDecision": "deny"' in out and "stale" in out


def test_dryrun_does_not_deny(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    out = run_gate(repo, tmp_path, mode="dryrun")
    assert '"systemMessage"' in out and "deny" not in out.split("systemMessage")[0]


def test_non_git_command_ignored(tmp_path):
    repo = make_repo(tmp_path)
    env = dict(os.environ, PYTHONPATH=str(HOOKS), JJ_HOME=str(tmp_path / "state"),
               JJ_GATE_COMMIT_INTEGRITY="enforce")
    env.pop("JJ_HOOK_ACTIVE", None)
    payload = {"tool_name": "Bash", "session_id": "s", "cwd": str(repo),
               "tool_input": {"command": "ls -la"}}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    assert r.returncode == 0 and r.stdout.strip() == ""
