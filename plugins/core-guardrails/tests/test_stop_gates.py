"""Stop-family gates: security-gate, test-gate and i18n-complete brought into the
dispatcher runtime (ADR-0027). Real dispatch.sh, real node, real vendored scripts - no
mocks. i18n-complete is used as the deterministic seeded-failure case because it needs no
external scanner (semgrep/osv-scanner/a test runner): a Stop-level check only
walks .xcstrings files (see vendor/i18n-complete.mjs collectTargets()), so a String
Catalog with one untranslated key is a reliable, fast, dependency-free failure."""
import json
import os
import pathlib
import subprocess
import sys

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "scripts"
DISPATCH = HOOKS / "dispatch.sh"
STOP_DIR = HOOKS / "Stop"
HOOKS_JSON = HOOKS.parent / "hooks.json"

BROKEN_XCSTRINGS = """{
  "sourceLanguage": "en",
  "strings": {
    "hello": {
      "localizations": {
        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
        "cs": {"stringUnit": {"state": "new", "value": ""}}
      }
    }
  },
  "version": "1.0"
}
"""


def make_repo(tmp_path: pathlib.Path, seed_broken_xcstrings: bool = False) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    if seed_broken_xcstrings:
        (repo / "Strings.xcstrings").write_text(BROKEN_XCSTRINGS)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def run_dispatch(repo: pathlib.Path, tmp_path: pathlib.Path, env_extra: dict | None = None,
                  timeout: int = 90) -> subprocess.CompletedProcess:
    payload = {"session_id": "stop-test", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    env = dict(os.environ, JJ_HOME=str(tmp_path / "state"), JJ_VAULT_ROOT=str(tmp_path / "novault"))
    env.pop("JJ_HOOK_ACTIVE", None)
    env.update(env_extra or {})
    return subprocess.run([str(DISPATCH), "Stop"], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=timeout)


def run_wrapper(script: str, payload: dict, tmp_path: pathlib.Path,
                 env_extra: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(HOOKS), JJ_HOME=str(tmp_path / "state"),
               JJ_VAULT_ROOT=str(tmp_path / "novault"))
    env.pop("JJ_HOOK_ACTIVE", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(STOP_DIR / script)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=timeout)


def telemetry_events(tmp_path: pathlib.Path) -> list[dict]:
    q = tmp_path / "state" / "telemetry" / "queue"
    events: list[dict] = []
    if not q.is_dir():
        return events
    for f in q.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


# ---- wiring: Stop dispatch reaches the three gates ----

def test_stop_wired_through_hooks_json():
    data = json.loads(HOOKS_JSON.read_text())
    stop = data["hooks"].get("Stop")
    assert stop, "hooks.json has no Stop event wired"
    cmd = stop[0]["hooks"][0]["command"]
    assert "dispatch.sh" in cmd and "Stop" in cmd


def test_stop_directory_has_all_three_gates():
    names = sorted(p.name for p in STOP_DIR.glob("*.py"))
    assert names == ["10_security_gate.py", "20_test_gate.py", "30_i18n_complete.py"]


def test_dispatch_stop_reaches_all_three_gates_and_allows_clean_repo(tmp_path):
    repo = make_repo(tmp_path)
    r = run_dispatch(repo, tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""
    checked = {e["detail"]["hook"] for e in telemetry_events(tmp_path) if e["event"] == "gate_checked"}
    assert checked == {"security-gate", "test-gate", "i18n-complete"}


# ---- enforce blocks on a seeded failure ----

def test_dispatch_stop_enforce_blocks_on_seeded_i18n_failure(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    r = run_dispatch(repo, tmp_path, {"JJ_GATE_I18N_COMPLETE": "enforce"})
    assert r.returncode == 2
    assert "blocked" in r.stderr
    fired = [e for e in telemetry_events(tmp_path)
             if e["event"] == "gate_fired" and e["detail"].get("hook") == "i18n-complete"]
    assert fired and fired[0]["detail"]["decision"] == "block"


def test_i18n_complete_wrapper_enforce_blocks_directly(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    r = run_wrapper("30_i18n_complete.py", payload, tmp_path,
                     {"JJ_GATE_I18N_COMPLETE": "enforce"})
    assert r.returncode == 2
    assert "TRANSLATION GATE FAILED" in r.stderr


# ---- dryrun does not block ----

def test_dispatch_stop_dryrun_does_not_block_on_same_failure(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    r = run_dispatch(repo, tmp_path, {"JJ_GATE_I18N_COMPLETE": "dryrun"})
    assert r.returncode == 0
    assert '"systemMessage"' in r.stdout
    assert "would block" in r.stdout
    fired = [e for e in telemetry_events(tmp_path)
             if e["event"] == "gate_fired" and e["detail"].get("hook") == "i18n-complete"]
    assert fired and fired[0]["detail"]["decision"] == "advisory"


def test_i18n_complete_wrapper_dryrun_does_not_block_directly(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    r = run_wrapper("30_i18n_complete.py", payload, tmp_path,
                     {"JJ_GATE_I18N_COMPLETE": "dryrun"})
    assert r.returncode == 0
    assert '"systemMessage"' in r.stdout and "TRANSLATION GATE FAILED" in r.stdout


# ---- mode-resolution edge cases shared by all three (lib.nodegate) ----

def test_off_mode_skips_before_running_node(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    r = run_wrapper("30_i18n_complete.py", payload, tmp_path,
                     {"JJ_GATE_I18N_COMPLETE": "off"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_missing_node_fails_open_as_advisory(tmp_path):
    repo = make_repo(tmp_path, seed_broken_xcstrings=True)
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    py_dir = str(pathlib.Path(sys.executable).parent)
    r = run_wrapper("30_i18n_complete.py", payload, tmp_path,
                     {"JJ_GATE_I18N_COMPLETE": "enforce", "PATH": f"/usr/bin:/bin:{py_dir}"})
    assert r.returncode == 0
    assert "node is not on PATH" in r.stdout


# ---- test-gate: preflight.toml [commands].test wins over autodetection (ADR-0029) ----

def _seed_scoped_repo(tmp_path: pathlib.Path, scoped_cmd: str) -> pathlib.Path:
    """package.json whose `npm test` always fails, plus a preflight.toml scoped command.
    If the vendored script still autodetected `npm test`, the gate would block."""
    repo = make_repo(tmp_path)
    (repo / "package.json").write_text(json.dumps(
        {"name": "t", "version": "0.0.0", "scripts": {"test": "exit 7"}}))
    (repo / "preflight.toml").write_text(
        f'languages = ["node"]\n\n[commands]\nbuild = "true"\ntest = "{scoped_cmd}"\n')
    return repo


def test_test_gate_prefers_preflight_scoped_command(tmp_path):
    repo = _seed_scoped_repo(tmp_path, "true")
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    r = run_wrapper("20_test_gate.py", payload, tmp_path, {"JJ_GATE_TEST_GATE": "enforce"},
                     timeout=60)
    assert r.returncode == 0, r.stderr


def test_test_gate_failing_scoped_command_still_blocks(tmp_path):
    repo = _seed_scoped_repo(tmp_path, "exit 3")
    payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
               "stop_hook_active": False}
    r = run_wrapper("20_test_gate.py", payload, tmp_path, {"JJ_GATE_TEST_GATE": "enforce"},
                     timeout=60)
    assert r.returncode == 2
    assert "TEST GATE FAILED" in r.stderr
