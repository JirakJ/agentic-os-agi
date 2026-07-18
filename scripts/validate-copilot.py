#!/usr/bin/env python3
"""validate-copilot: offline schema lint for generated Copilot artifacts. Fails CI when a
canonical asset cannot be represented on a Copilot surface.

Checks:
  1. Every SKILL.md: frontmatter name == parent dir, name <= 64 chars lowercase-hyphen,
     description present and <= 1024 chars (Agent Skills spec).
  2. Every .github/instructions/*.instructions.md has an applyTo frontmatter.
  3. Every .github/agents/*.agent.md: model (if present) is a string, not an array.
  4. .github/copilot-instructions.md stays under a line budget (it always loads whole).
  5. Every prompt file has a description.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_REPO_WIDE_LINES = 120
errors: list[str] = []


def fm(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def check_skills() -> None:
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")) + \
                 sorted(ROOT.glob(".github/skills/*/SKILL.md")):
        meta = fm(skill)
        name = meta.get("name", "")
        if name != skill.parent.name:
            errors.append(f"{skill}: name '{name}' != directory '{skill.parent.name}' "
                          "(Copilot silently skips mismatched skills)")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name or ""):
            errors.append(f"{skill}: name must be <=64 chars, lowercase alphanumeric+hyphens")
        desc = meta.get("description", "")
        if not desc:
            errors.append(f"{skill}: missing description")
        elif len(desc) > 1024:
            errors.append(f"{skill}: description {len(desc)} chars > 1024 (spec limit)")


def check_instructions() -> None:
    for ins in sorted(ROOT.glob(".github/instructions/*.instructions.md")):
        if "applyTo" not in fm(ins):
            errors.append(f"{ins}: missing applyTo frontmatter")


def check_agents() -> None:
    for ag in sorted(ROOT.glob(".github/agents/*.agent.md")):
        meta = fm(ag)
        model = meta.get("model", "")
        if model.startswith("["):
            errors.append(f"{ag}: model must be a single string (arrays break Copilot CLI)")
        if not meta.get("description"):
            errors.append(f"{ag}: missing description")


def check_repo_wide() -> None:
    f = ROOT / ".github" / "copilot-instructions.md"
    if f.exists():
        n = len(f.read_text(encoding="utf-8").splitlines())
        if n > MAX_REPO_WIDE_LINES:
            errors.append(f"{f}: {n} lines > budget {MAX_REPO_WIDE_LINES} "
                          "(this file always loads whole - keep it lean)")


def check_prompts() -> None:
    for p in sorted(ROOT.glob(".github/prompts/*.prompt.md")):
        if not fm(p).get("description"):
            errors.append(f"{p}: missing description")


def main() -> int:
    for fn in (check_skills, check_instructions, check_agents, check_repo_wide,
               check_prompts):
        fn()
    if errors:
        print("validate-copilot: FAILED")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("validate-copilot: all Copilot artifacts valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
