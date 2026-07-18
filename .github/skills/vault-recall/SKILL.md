---
name: vault-recall
description: Retrieve what the user already wrote, decided or captured, from their Obsidian vault and the agent's episodic memory, using hybrid BM25 + vector search over a local index. Use this whenever the user asks what they know or previously decided about something, says "what do I know about X", "did I write anything on Y", "check my notes", "recall", "what did we decide", "have I looked at this before", or refers to prior work without restating it — and proactively before answering any question where their own prior notes would sharpen the answer or reveal an earlier decision. Also use it when the user mentions a project, tool or person by a name you do not recognise.
allowed-tools: Bash, Read
context: fork
metadata:
  version: 1.0.0
  layer: L4-index
---

# Vault Recall

Answer from what the user already knows before answering from what you know. A prior decision in
their vault beats a good general answer, every time — and contradicting their own notes without
noticing is the worst failure mode this skill exists to prevent.

## Query it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recall.py" "what did I decide about jq" --limit 5
```

Returns ranked snippets with paths, not documents. That is deliberate: a note dumped into context
costs thousands of tokens and buries the answer. Read the full note with `Read` **only** if a
snippet indicates the detail is there and it matters.

Options:

| Flag | Use |
|---|---|
| `--limit N` | default 5; go to 8-10 when the question is broad |
| `--layer L3-knowledge` | the user's own notes only |
| `--layer L2-episodic` | what past sessions recorded only |
| `--json` | when you need to process the hits rather than read them |

## Reading the results

Each hit is tagged with why it ranked:

- `keyword #N` — matched terms. Trustworthy for names, tools, ADR ids, project names.
- `semantic #N` — matched meaning without sharing vocabulary. Trustworthy for "how do we usually
  handle X" questions.
- `keyword #N + semantic #N` — both arms agree. The strongest signal available.

`[BM25 only]` in the footer means the vector arm is off (no model installed). Recall still works;
it just cannot find notes that share no words with the query. Do not treat an empty result as proof
of absence in that mode — rephrase with the terms the note would actually use.

## Fork the context

This skill runs with `context: fork`. Search output — a dozen snippets, most irrelevant — stays out
of the main thread; only what you carry back survives. Carry back the answer and the paths, not the
transcript of the search.

## When recall finds a contradiction

If a note says the opposite of what you were about to say, the note wins on facts about *their*
system, their decisions, their history. Say so explicitly:

> Your note in `20-Projects/cascade-router.md` says the tier-2/3 gate is where the savings are —
> that contradicts what I was about to suggest. Going with the note.

You are not required to agree with their reasoning. You *are* required to notice it and surface the
conflict rather than silently overwriting it.

## Query construction

The index searches chunks, not whole notes, so specific queries beat broad ones. Use the terms the
note itself would use, not the terms of the question:

- Good: `hook latency python cold start` — the words that would appear in the note
- Bad: `how fast are the hooks` — the words of the question

If the first query misses, try again with different vocabulary before concluding nothing is there.
Two failed queries with different terms is evidence; one is not.

## Stale index

The index refreshes at session end and on demand. If recall returns nothing for something you know
exists:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/index_vault.py" --stats     # is it indexed at all?
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/index_vault.py"             # incremental refresh
```

The index is derived data — `--rebuild` is always safe and never loses anything (ADR-0003).
