---
description: Rebuild or refresh the local retrieval index over the vault and episodic memory
argument-hint: "[--rebuild] [--stats] [--vault PATH]"
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/index_vault.py" $ARGUMENTS
```

Incremental by default: a file is re-read only when its mtime moved *and* its hash actually changed.

The index is derived data (ADR-0003) — `--rebuild` is always safe and loses nothing. If recall
returns nothing for something that definitely exists, this is the first thing to try.

`[BM25 only]` in the output means the vector arm is off. The reason is printed. BM25 recall is
unaffected; only semantic matching is lost.
