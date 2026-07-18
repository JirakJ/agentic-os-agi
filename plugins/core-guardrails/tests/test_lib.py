"""Unit tests for the shared hook library."""
import json
import subprocess
import sys
import pathlib

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "scripts"


def run_hook(rel: str, payload: dict, env_extra: dict | None = None) -> tuple[int, str]:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(HOOKS)
    env.pop("JJ_HOOK_ACTIVE", None)
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, str(HOOKS / rel)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    return r.returncode, r.stdout


def test_allowlists_path_match():
    from lib import allowlists
    assert allowlists.path_matches("/x/.env", "secret_paths")
    assert allowlists.path_matches("a/b/id_rsa", "secret_paths")
    assert not allowlists.path_matches("src/main.py", "secret_paths")


def test_allowlists_regex():
    from lib import allowlists
    assert allowlists.regex_hits("git push --force origin main", "destructive_bash")
    assert not allowlists.regex_hits("git push origin feature", "destructive_bash")


def test_security_gate_denies_secret(tmp_path):
    rc, out = run_hook("PreToolUse/20_security_gate.py",
                       {"tool_name": "Read", "session_id": "t",
                        "tool_input": {"file_path": str(tmp_path / ".env")}},
                       {"JJ_HOME": str(tmp_path / "state"),
                        "JJ_VAULT_ROOT": str(tmp_path / "novault")})
    assert rc == 0 and '"permissionDecision": "deny"' in out


def test_security_gate_allows_normal(tmp_path):
    rc, out = run_hook("PreToolUse/20_security_gate.py",
                       {"tool_name": "Read", "session_id": "t",
                        "tool_input": {"file_path": str(tmp_path / "main.py")}},
                       {"JJ_HOME": str(tmp_path / "state")})
    assert rc == 0 and out.strip() == ""


def test_no_placeholder_dryrun_advisory(tmp_path):
    rc, out = run_hook("PreToolUse/40_no_placeholder.py",
                       {"tool_name": "Write", "session_id": "t",
                        "tool_input": {"file_path": str(tmp_path / "x.py"),
                                       "content": "def f():\n    pass  # TODO implement\n"}},
                       {"JJ_HOME": str(tmp_path / "state"),
                        "JJ_GATE_NO_PLACEHOLDER": "dryrun"})
    assert rc == 0 and "systemMessage" in out


def test_no_placeholder_enforce_denies(tmp_path):
    rc, out = run_hook("PreToolUse/40_no_placeholder.py",
                       {"tool_name": "Write", "session_id": "t",
                        "tool_input": {"file_path": str(tmp_path / "x.py"),
                                       "content": "raise NotImplementedError\n"}},
                       {"JJ_HOME": str(tmp_path / "state"),
                        "JJ_GATE_NO_PLACEHOLDER": "enforce"})
    assert rc == 0 and '"permissionDecision": "deny"' in out


def test_no_placeholder_escape_hatch(tmp_path):
    rc, out = run_hook("PreToolUse/40_no_placeholder.py",
                       {"tool_name": "Write", "session_id": "t",
                        "tool_input": {"file_path": str(tmp_path / "x.py"),
                                       "content": "# jj-allow-placeholder\n# TODO tracked in ADR\n"}},
                       {"JJ_HOME": str(tmp_path / "state"),
                        "JJ_GATE_NO_PLACEHOLDER": "enforce"})
    assert rc == 0 and out.strip() == ""
