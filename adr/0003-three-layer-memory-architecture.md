---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [skill/vault-recall, skill/vault-capture, manifest/memory-obsidian]
supersedes: []
superseded-by: []
---

# ADR-0003 — Memory splits into four layers with one source of truth each

## Context and Problem Statement

"Memory" collapses four different things: the fleet's procedural knowledge (how to do the work),
what happened in past sessions, the human's knowledge base, and a fast index over all of it. They
have different lifetimes, different write patterns and different consequences when lost. Storing
them together means the store is wrong for at least three of them, and it makes "what do we
version?" unanswerable.

## Decision Drivers

* Each piece of state needs exactly one source of truth, or reconciliation becomes a permanent tax
* Session working memory is high-churn noise; committing it would drown the core-logic history that
  ADR-0002's rollback story depends on
* A semantic index is derived data — if it cannot be rebuilt from its sources, it is a liability
* Retrieval must cost few tokens: dumping whole notes into context defeats the purpose
* No component may call an LLM API — the whole system runs inside Claude Code

## Considered Options

* One store: everything in the vault
* Two stores: Git for core, vault for everything else
* Four layers: Git core, Git durable episodic, vault knowledge, SQLite index

## Decision Outcome

Chosen option: "Four layers", because each layer has a genuinely different lifetime and failure
mode, and collapsing any two of them makes one of them worse:

| Layer | Store | Contents | Versioned | Rebuildable |
|---|---|---|---|---|
| L1 core | Git (this repo) | skills, agents, hooks, commands, instructions, ADRs | yes | no |
| L2 episodic | Git `memory/` + `${CLAUDE_PLUGIN_DATA}` | run summaries, durable learned facts / session scratch | durable: yes; scratch: no | no / yes |
| L3 knowledge | Obsidian vault | notes, long-form knowledge, user data | separately (ADR-0004) | no |
| L4 index | SQLite FTS5 + sqlite-vec | embeddings and keyword index over L2+L3 | **no** | **yes** |

The rule that makes it operable: **L4 is never a source of truth.** Delete it and `vault-index.py`
rebuilds it. Anything that only exists in L4 is a bug.

### Consequences

* Good, because "should this be committed?" has a mechanical answer: is it L1 or durable L2? commit.
  L4 or scratch? never
* Good, because the index can be blown away and rebuilt on any machine — no sync, no migration, no
  backup story
* Good, because retrieval returns snippets from the index rather than notes into context, so recall
  costs tens of tokens instead of thousands
* Bad, because four layers is four things to explain, and the L2 boundary (durable vs scratch) is a
  judgement call that will occasionally be got wrong
* Bad, because L4 duplicates content from L2 and L3, so a stale index silently returns stale
  answers — staleness detection (mtime + content hash) is now mandatory, not optional

### Confirmation

The architecture is wrong if: (a) deleting `.index/` ever loses information that cannot be
rebuilt, (b) recall latency p95 exceeds 150 ms on a vault under ~10k notes, or (c) the repo's
commit history becomes dominated by memory churn rather than logic changes. Any of the three means
a layer is holding state it should not.

## Pros and Cons of the Options

### One store: everything in the vault

* Good, because one place to look
* Bad, because core logic in a vault cannot be loaded by Claude Code without an export step
* Bad, because no versioning story for the part that most needs one

### Two stores: Git for core, vault for everything else

* Good, because it is the smallest split that solves ADR-0001
* Neutral, because Obsidian's search would serve retrieval, poorly but adequately
* Bad, because session scratch would land in the vault and pollute a hand-curated knowledge base
  with machine noise
* Bad, because no fast semantic layer — every recall is a full-text grep, and hybrid ranking is
  impossible

### Four layers

* Good, because each layer's store matches its access pattern
* Good, because the rebuildable index means no sync or backup burden for the largest artifact
* Bad, because it is the most conceptual overhead of the three

## More Information

L4 is a cache in the strict sense: content-addressed by file hash, invalidated by mtime, rebuilt by
one command. See ADR-0007 for the retrieval backend, ADR-0004 for how L3 is versioned.
