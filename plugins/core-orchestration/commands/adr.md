---
description: Create a MADR decision record, or list the existing ones
argument-hint: "\"<title>\" [--supersedes NNNN] | --list"
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adr_new.py" $ARGUMENTS
```

If a title was given, the script created the record — now fill it in. Read the `adr-workflow` skill
for what each section is for. The sections that carry weight:

- **Decision Drivers** — only the ones that actually rule an option out. Numbers where numbers exist.
- **Considered Options** — at least two, argued symmetrically. Do not strawman the rejected ones.
- **Consequences** — the Bad half is what earns the record its keep. If you cannot name a downside,
  go back and think harder about the trade-off.
- **Confirmation** — falsifiable. "Revisit if p95 exceeds 200 ms", not "revisit if problems arise".

Read the affected components before writing. An ADR written from a summary rather than the code
describes a system that does not exist.

Then commit it alone: `docs(adr): add ADR-NNNN on <topic>` — before the code it justifies.
