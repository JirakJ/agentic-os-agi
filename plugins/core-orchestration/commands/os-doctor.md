---
description: Validate every plugin, skill, agent, hook and decision record in the marketplace
argument-hint: "[--manifests|--skills|--adr|--hooks]"
---

Run the marketplace validator and report what it finds.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" $ARGUMENTS
```

If it reports errors, fix them now — do not defer. Each finding names the file and the exact
problem. The failure modes it catches are all silent ones: a component under `.claude-plugin/`
loads without error and exposes nothing; a version drift means installs never update; a dangling
ADR reference means the reasoning behind a component is gone.

If it is clean, say so in one line and stop.
