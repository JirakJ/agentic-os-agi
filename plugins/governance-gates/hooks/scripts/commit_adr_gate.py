#!/usr/bin/env python3
"""Stop gate: core logic never ends a turn uncommitted, and behaviour never changes undocumented.

Two checks, in order of severity:

  1. Dirty core logic  → block. An uncommitted skill is a skill you cannot roll back. This is the
     whole premise of the system: one component per commit, so `git revert <sha>` restores exactly
     one thing.

  2. Behaviour changed without an ADR → block. Prose fixes and version bumps are exempt; a changed
     trigger surface, a narrowed tool grant, a new blocking rule is not.

Both emit decision=block with the offending paths and the commands to fix them, so Claude can
resolve it in the same turn rather than bouncing to the user.

Loop protection: `stop_hook_active` means we already blocked once this turn and Claude is retrying
— blocking again would spin. Let it through and let the human see the state.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (classify, component_id, git, in_git_repo, marketplace_root,  # noqa: E402
                  project_dir, proceed, read_event, stop_block)

# A change is "behavioural" — and so needs a decision record — when it moves a contract rather
# than the words describing one.
BEHAVIOURAL_MARKERS = (
    re.compile(r"^[+-]\s*(?:allowed-tools|tools|model|context|disable-model-invocation):", re.M),
    re.compile(r"^[+-]\s*description:", re.M),
    re.compile(r'^[+-]\s*"(?:dependencies|stability|layer)"', re.M),
    re.compile(r"^[+-].*(?:permissionDecision|decision.*block|exit\(2\)|sys\.exit\(2\))", re.M),
    re.compile(r'^[+-]\s*"(?:hooks|matcher|command)"\s*:', re.M),
)

EXEMPT_KINDS = {"decision-record"}


def dirty_core(root: Path) -> dict[str, list[str]]:
    """Uncommitted core paths, grouped by component id.

    Porcelain v1 is `XY PATH` — two status columns, a space, then the path — so the path begins at
    index 3. The output must be read UNSTRIPPED: for an unstaged edit the first column is a space
    (` M path`), and stripping it shifts the slice and drops the leading path character.
    """
    status = git("status", "--porcelain", "--untracked-files=all", cwd=root, strip=False)
    grouped: dict[str, list[str]] = {}
    for line in status.split("\n"):
        if len(line) < 4:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:  # rename: XY ORIG -> PATH
            rel = rel.split(" -> ", 1)[1]
        kind = classify(rel)
        if kind and kind not in EXEMPT_KINDS:
            grouped.setdefault(component_id(rel), []).append(rel)
    return grouped


def staged_or_recent_adr(root: Path) -> bool:
    """An ADR is present for this change if one is staged, or landed in the last few commits."""
    staged = git("diff", "--cached", "--name-only", cwd=root)
    if any(line.startswith("adr/") for line in staged.splitlines()):
        return True
    recent = git("log", "-5", "--name-only", "--pretty=format:", cwd=root)
    return any(line.startswith("adr/") for line in recent.splitlines())


def behavioural_change(root: Path, paths: list[str]) -> str | None:
    """The first marker indicating a contract moved, or None for prose-only edits."""
    for rel in paths:
        diff = git("diff", "HEAD", "--unified=0", "--", rel, cwd=root)
        if not diff:
            diff = git("diff", "--cached", "--unified=0", "--", rel, cwd=root)
        if not diff and (root / rel).is_file():
            tracked = git("ls-files", "--error-unmatch", rel, cwd=root)
            if not tracked:
                return f"{rel} is a new component"
        for marker in BEHAVIOURAL_MARKERS:
            if marker.search(diff):
                return f"{rel} changes a contract, not just prose"
    return None


def main() -> None:
    event = read_event()

    if event.get("stop_hook_active"):
        proceed()  # already blocked this turn — do not spin

    cwd = project_dir(event)
    root = marketplace_root(cwd)
    if root is None or not in_git_repo(root):
        proceed()

    grouped = dirty_core(root)
    if not grouped:
        proceed()

    lines = ["commit-adr-gate: core logic is uncommitted. One component per commit, or you cannot "
             "roll it back.\n"]
    for cid, paths in sorted(grouped.items()):
        lines.append(f"  {cid}")
        for path in sorted(paths):
            lines.append(f"    {path}")

    lines.append("\nCommit each component separately — stage by path, never `git add -A`:\n")
    for cid, paths in sorted(grouped.items()):
        kind, _, name = cid.partition("/")
        scope = {"skill": "skill", "agent": "agent", "hook": "hook", "command": "command",
                 "manifest": "manifest", "marketplace": "marketplace",
                 "instruction": "instruction"}.get(kind, kind)
        target = f"{scope}/{name}" if scope not in {"marketplace", "instruction"} else scope
        lines.append(f"  git add {' '.join(sorted(paths))}")
        lines.append(f"  git commit -m '<type>({target}): <subject>'\n")

    all_paths = [p for paths in grouped.values() for p in paths]
    why = behavioural_change(root, all_paths)
    if why and not staged_or_recent_adr(root):
        lines.append(
            f"A decision record is also required — {why}.\n"
            f"Write it first, commit it on its own, then reference it from the implementation:\n\n"
            f"  python3 plugins/core-orchestration/scripts/adr_new.py '<decision>'\n"
            f"  git add adr/NNNN-*.md && git commit -m 'docs(adr): add ADR-NNNN on <topic>'\n"
            f"  # then the implementation commit carries:  Refs: ADR-NNNN\n"
        )

    lines.append("If the change was exploratory: git checkout -- <paths>")
    stop_block("\n".join(lines))


if __name__ == "__main__":
    main()
