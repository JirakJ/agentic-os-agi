#!/usr/bin/env python3
"""PostToolUse gate: a core component never stays broken past the edit that broke it.

Runs doctor.py scoped to whatever was just written. Blocks with exit 2 so Claude gets the findings
back immediately and fixes them in the same turn — a broken manifest discovered at commit time is
a broken manifest you have already built three things on top of.

Only fires on core logic. Editing a README costs nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import block, classify, marketplace_root, proceed, project_dir, read_event, tool_paths  # noqa: E402

# Which doctor check answers for which component kind. Scoping keeps the hook inside its latency
# budget — a full run walks every plugin.
SCOPE = {
    "skill": "--skills",
    "agent": "--skills",
    "manifest": "--manifests",
    "marketplace": "--manifests",
    "hook": "--hooks",
    "decision-record": "--adr",
}


def main() -> None:
    event = read_event()
    if event.get("tool_name") not in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        proceed()

    root = marketplace_root(project_dir(event))
    if root is None:
        proceed()

    scopes: set[str] = set()
    for raw in tool_paths(event):
        try:
            rel = str(Path(raw).resolve().relative_to(root))
        except ValueError:
            continue
        kind = classify(rel)
        if kind and kind in SCOPE:
            scopes.add(SCOPE[kind])

    if not scopes:
        proceed()

    doctor = root / "plugins" / "core-orchestration" / "scripts" / "doctor.py"
    if not doctor.is_file():
        proceed()

    try:
        result = subprocess.run(
            [sys.executable, str(doctor), *sorted(scopes)],
            cwd=root, capture_output=True, text=True, timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        proceed()  # the validator failing is not the user's problem

    if result.returncode == 0:
        proceed()

    block(
        "manifest-validator: the component you just wrote does not validate.\n\n"
        f"{result.stdout.strip()}\n\n"
        "Fix it now, in this turn. A broken manifest loads silently and does nothing, so it will "
        "not surface again until something mysteriously fails to trigger."
    )


if __name__ == "__main__":
    main()
