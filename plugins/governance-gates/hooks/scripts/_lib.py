"""Shared runtime for agentic OS hooks.

Wraps the Claude Code hook I/O contract so individual gates stay short and cannot get the protocol
subtly wrong. stdlib only, no imports beyond what a cold start already pays for — hooks run
synchronously on the critical path and stack, so every import is latency on every tool call.

Protocol:
    stdin   JSON event payload
    exit 0  proceed (stdout shown to the user in transcript mode)
    exit 2  block — stderr is fed back to Claude as the reason
    other   non-blocking error — logged, execution continues

JSON on stdout gives finer control than exit codes: permissionDecision for PreToolUse,
additionalContext for injecting facts, decision=block for Stop.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Core logic paths — the components whose change requires an atomic commit and, if behaviour
# moves, a decision record. Kept as (glob, component-kind) so callers can label findings.
CORE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("plugins/*/skills/*/SKILL.md", "skill"),
    ("plugins/*/skills/*/skill.json", "skill"),
    ("plugins/*/skills/*/reference/*", "skill"),
    ("plugins/*/agents/*.md", "agent"),
    ("plugins/*/hooks/*", "hook"),
    ("plugins/*/hooks/scripts/*", "hook"),
    ("plugins/*/commands/*.md", "command"),
    ("plugins/*/.claude-plugin/plugin.json", "manifest"),
    (".claude-plugin/marketplace.json", "marketplace"),
    ("CLAUDE.md", "instruction"),
    ("*/CLAUDE.md", "instruction"),
    ("adr/*.md", "decision-record"),
)


def read_event() -> dict:
    """Parse the event payload. A malformed payload must never block the user's work."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def plugin_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def plugin_data() -> Path:
    """Per-plugin state that survives updates. Falls back to the XDG-ish default."""
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    path = Path(raw) if raw else Path.home() / ".claude" / "plugins" / "data" / "governance-gates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_dir(event: dict) -> Path:
    return Path(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def git(*args: str, cwd: Path, strip: bool = True) -> str:
    """Run git, swallowing failure. Absence of a repo is not the hook's problem to report.

    strip defaults True for the common case (a SHA, a branch name). Pass strip=False for
    `--porcelain`, whose leading status columns are significant — stripping ` M path` to
    `M path` shifts every subsequent slice by one and silently eats the first path character.
    """
    try:
        result = subprocess.run(
            ("git", *args), cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip() if strip else result.stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def in_git_repo(cwd: Path) -> bool:
    return git("rev-parse", "--is-inside-work-tree", cwd=cwd) == "true"


def marketplace_root(start: Path) -> Path | None:
    """Nearest ancestor holding .claude-plugin/marketplace.json, or None if outside one."""
    here = start.resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    return None


def classify(rel_path: str) -> str | None:
    """Return the component kind for a repo-relative path, or None if it is not core logic."""
    from fnmatch import fnmatch

    normalised = rel_path.lstrip("./")
    for pattern, kind in CORE_PATTERNS:
        if fnmatch(normalised, pattern):
            return kind
    return None


def component_id(rel_path: str) -> str:
    """Stable component id for a core path: 'skill/vault-recall', 'hook/secret-guard'."""
    kind = classify(rel_path)
    parts = Path(rel_path).parts
    if kind == "skill" and "skills" in parts:
        return f"skill/{parts[parts.index('skills') + 1]}"
    if kind == "agent":
        return f"agent/{Path(rel_path).stem}"
    if kind == "command":
        return f"command/{Path(rel_path).stem}"
    if kind == "hook":
        return f"hook/{Path(rel_path).stem.replace('_', '-')}"
    if kind == "manifest" and "plugins" in parts:
        return f"manifest/{parts[parts.index('plugins') + 1]}"
    return f"{kind or 'file'}/{Path(rel_path).name}"


def tool_paths(event: dict) -> list[str]:
    """Every filesystem path a tool event touches, absolute where the payload gives one."""
    tool_input = event.get("tool_input") or {}
    found: list[str] = []
    for key in ("file_path", "notebook_path", "path"):
        if isinstance(tool_input.get(key), str):
            found.append(tool_input[key])
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
            found.append(edit["file_path"])
    return found


# ── responses ────────────────────────────────────────────────────────────────────────────────

def proceed(message: str = "") -> None:
    if message:
        print(message)
    sys.exit(0)


def block(reason: str) -> None:
    """Exit 2 — Claude receives `reason` on stderr and must deal with it."""
    print(reason, file=sys.stderr)
    sys.exit(2)


def deny(reason: str) -> None:
    """PreToolUse: refuse the call without ending the turn."""
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.exit(0)


def ask(reason: str) -> None:
    """PreToolUse: bounce the decision to the human."""
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.exit(0)


def add_context(event_name: str, context: str) -> None:
    """Inject a fact into Claude's context without blocking anything."""
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }, sys.stdout)
    sys.exit(0)


def stop_block(reason: str) -> None:
    """Stop/SubagentStop: refuse to finish the turn and tell Claude why."""
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.exit(0)
