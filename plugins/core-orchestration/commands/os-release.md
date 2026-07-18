---
description: Cut a SemVer release of a plugin, or roll one back by re-pinning
argument-hint: "<plugin> [--bump major|minor|patch] [--pin vX.Y.Z] [--dry-run] | --status"
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" $ARGUMENTS
```

**Always `--dry-run` first** and read the plan before the real run.

Before cutting: the tree must be clean and `doctor.py` must pass — the script enforces both.

Check the derived bump against reality. The script reads Conventional Commits, but the commits can
understate what changed: a hook that starts blocking something is a **major** bump even if every
commit message says `fix`. What changed for the consumer decides, not what the message says.

Before a major, check who depends on the plugin:

```bash
grep -r '"dependencies"' plugins/*/.claude-plugin/plugin.json
```

A major on `core-orchestration` disables `governance-gates` (`^1.0.0`) with
`dependency-version-unsatisfied` until its range widens. Bump both in the same release, separate
commits.

Publish with `git push origin main --follow-tags` — an untagged release does not trigger the
workflow.
