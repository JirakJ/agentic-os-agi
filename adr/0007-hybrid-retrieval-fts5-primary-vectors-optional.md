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

# ADR-0007 — Retrieval is FTS5-first with an optional local vector rerank

## Context and Problem Statement

L4 (ADR-0003) needs to surface the right note at the right moment for few tokens, with no LLM API
call anywhere in the path. Vector search is the reflex answer, but it drags in a model download, a
model file, and an inference dependency — and it degrades to nothing when any of those is missing.
A recall path that only works after a successful `huggingface.co` fetch is a recall path that does
not work.

## Decision Drivers

* No LLM API calls — the constraint is architectural, so embeddings must be local or absent
* Recall must work on a fresh clone with zero model downloads, or the first-run experience is a
  stack trace
* p95 recall under ~150 ms on a vault of ~10k notes
* A personal vault's queries are mostly lexical — project names, tool names, ADR ids, people. BM25
  is genuinely strong on exactly that distribution
* The index must be rebuildable from source (ADR-0003), so it cannot be the only home of anything

## Considered Options

* FTS5 only (BM25 keyword search)
* sqlite-vec only, embeddings via a local model
* FTS5 primary + optional sqlite-vec rerank, fused by Reciprocal Rank Fusion
* An external vector service (Chroma, Qdrant, LanceDB)

## Decision Outcome

Chosen option: "FTS5 primary + optional sqlite-vec rerank", because it makes the dependency
*additive* rather than *required*: recall works fully on stdlib `sqlite3` alone, and gets better —
not merely different — when `sqlite-vec` + `model2vec` are present.

Both arms feed Reciprocal Rank Fusion (k=60). BM25 alone answers "the ADR about jq"; the vector arm
answers "how do we decide when something needs a decision record" — a query sharing no terms with
its target. RRF needs no score calibration between the two, which is what makes the optional arm
droppable without retuning.

`model2vec` (potion-base-8M, 256-dim static embeddings) is the vector backend: pure NumPy
inference, no torch, ~30 MB, sub-millisecond per chunk. Its weakness — static embeddings, no
context sensitivity — is acceptable precisely because BM25 carries the lexical half.

### Consequences

* Good, because `git clone` → `vault-index.py` → working recall, with no model, no network, no
  install beyond python3
* Good, because RRF means the vector arm can appear or vanish between runs without breaking ranking
* Good, because sqlite-vec is a single C extension against a file — no service, no port, no daemon
* Good, because everything is local, so the no-API-calls constraint holds by construction rather
  than by policy
* Bad, because two ranking arms mean two failure modes and a fusion step to reason about. A bad
  BM25 hit and a bad vector hit can reinforce each other into a confidently wrong top result
* Bad, because the first vector-enabled run downloads ~30 MB from `huggingface.co`. That is a real
  network dependency at setup time, even though steady-state is offline
* Bad, because static embeddings are meaningfully weaker than contextual ones on paraphrase-heavy
  queries. Accepted: the alternative is torch

### Confirmation

Wrong if: recall p95 exceeds 150 ms at ~10k notes; or the vector arm's contribution to top-5 hits
is under ~10% over a month of real queries (then it is not paying for its complexity and FTS5-only
is the right answer); or `.index/` ever holds something not rebuildable from L2/L3.

## Pros and Cons of the Options

### FTS5 only

* Good, because zero dependencies, stdlib `sqlite3`, instant
* Good, because BM25 is genuinely strong on a personal vault's proper-noun-heavy queries
* Bad, because it cannot answer a question that shares no vocabulary with its answer — the exact
  case where recall earns its keep

### sqlite-vec only

* Good, because one ranking path, one mental model
* Bad, because it hard-fails without a model — no model, no recall at all
* Bad, because static embeddings underperform BM25 on exact-term queries, which are the majority.
  Dropping the lexical arm gives up the strong case to improve the weak one

### FTS5 + optional sqlite-vec, RRF

* Good, because each arm covers the other's blind spot; the dependency is additive
* Bad, because two arms, two failure modes, one fusion parameter

### External vector service

* Good, because best-in-class ANN, mature tooling
* Bad, because a daemon, a port and a lifecycle for a single-user vault on one laptop
* Bad, because the index stops being a rebuildable file and becomes infrastructure with a backup story

## Implementation note — the KNN floor

KNN has no inherent similarity floor: `WHERE embedding MATCH ? AND k = N` always returns N rows,
however far away they are. Left raw, that means a query with no genuine match still returns its
nearest neighbours, and the vector arm confidently surfaces unrelated notes — the "confidently
wrong" failure this record's Consequences already flagged, made concrete.

The guard: embeddings are L2-normalised at storage and query time, which maps cosine distance onto
L2 as d² = 2(1 − cos) — identical vectors at 0, orthogonal at √2 ≈ 1.414. A distance ceiling
(`VEC_MAX_DISTANCE`, default 1.40, just under orthogonal) drops near-orthogonal neighbours before
they reach RRF. Normalisation is what makes the threshold backend-independent: it is rooted in the
geometry, not in whatever scale a particular model happens to emit, so it holds for model2vec today
and any replacement tomorrow. The ceiling is deliberately generous — it removes the unrelated, not
the merely loose, because the vector arm is supplementary (FTS5 is primary) and RRF already gives
weak matches little rank weight.

This surfaced during testing: a no-match query returned three phantom hits. The fix is the
threshold; the lesson is that "optional second arm" has to include "and it can decline to answer".

## More Information

sqlite-vec benchmarks (Alex Garcia, v0.1.0): 384-dim vectors, 100k rows, brute-force KNN on an M1
Mac mini — under 75 ms. The vault sits two orders of magnitude below that, so the vector arm is not
the latency risk; chunking and file I/O during reindex are.

`VEC_MAX_DISTANCE` is overridable via `$AGENTIC_OS_VEC_MAX_DISTANCE` for tuning against a real
corpus — lower it if recall surfaces loose matches, raise it toward √2 if it drops good ones.

Revisit if MLX ships a first-class embedding path with a comparable footprint — the Apple Silicon
alignment would be worth a supersede, not an edit.
