---
description: Search the Obsidian vault and episodic memory for what was already written or decided
argument-hint: "<query> [--limit N] [--layer L2-episodic|L3-knowledge]"
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recall.py" $ARGUMENTS
```

Report what came back: the answer, and the paths it came from. Read a full note with `Read` only if
a snippet shows the detail is there and it matters — snippets exist so recall costs tens of tokens
instead of thousands.

If a note contradicts what you were about to say, the note wins on facts about the user's own
systems and decisions. Surface the conflict explicitly rather than quietly overwriting it.

`[BM25 only]` in the footer means the vector arm is off, so a query sharing no vocabulary with its
target will miss. Rephrase using the terms the note itself would use before concluding nothing is
there.
