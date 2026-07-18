"""Preflight pipeline test against a throwaway python repo (attestation red -> green)."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable


def make_repo(tmp_path: pathlib.Path, code: str) -> pathlib.Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "app.py").write_text(code)
    (repo / "preflight.toml").write_text(
        'schema_version = 1\nproject_type = "library"\nlanguages = ["python"]\n'
        '[commands]\nlint = "python3 -m compileall -q ."\n'
        'test = "python3 -c \'import app\'"\n')
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    return repo


def run_preflight(repo: pathlib.Path) -> tuple[int, dict]:
    r = subprocess.run([PY, str(ROOT / "scripts" / "preflight.py")], cwd=repo,
                       capture_output=True, text=True, timeout=180)
    tree = subprocess.run(["git", "write-tree"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    att_file = repo / ".git" / "jj-attest" / f"{tree}.json"
    att = json.loads(att_file.read_text()) if att_file.exists() else {}
    return r.returncode, att


def test_red_on_syntax_error(tmp_path):
    repo = make_repo(tmp_path, "def broken(:\n")
    rc, att = run_preflight(repo)
    assert rc == 1 and att.get("overall") == "red"
    assert att["results"]["lint"]["status"] == "fail"


def test_green_on_valid_code_and_tree_keyed(tmp_path):
    repo = make_repo(tmp_path, "x = 41 + 1\n")
    rc, att = run_preflight(repo)
    assert rc == 0, att
    assert att.get("overall") == "green"
    tree = subprocess.run(["git", "write-tree"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    assert att["tree_hash"] == tree and att["ttl_s"] == 1800
