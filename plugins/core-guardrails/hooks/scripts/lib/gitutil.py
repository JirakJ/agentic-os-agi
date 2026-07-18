"""Safe git helpers for hooks. Fixed argv (never shell strings), short timeouts."""
from __future__ import annotations

import subprocess

def run(args: list[str], cwd: str | None = None, timeout: int = 4) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)

def toplevel(cwd: str | None = None) -> str | None:
    r = run(["rev-parse", "--show-toplevel"], cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None

def write_tree(cwd: str | None = None) -> str | None:
    r = run(["write-tree"], cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None

def head(cwd: str | None = None) -> str:
    r = run(["rev-parse", "HEAD"], cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else ""

def status_porcelain(cwd: str | None = None) -> str:
    r = run(["status", "--porcelain"], cwd=cwd, timeout=6)
    return r.stdout if r.returncode == 0 else ""
