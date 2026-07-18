---
name: adr-workflow
description: Write and maintain MADR 4.0.0 architecture decision records for the agentic OS. Use this whenever a change alters behaviour, contracts, policy or architecture — a skill's contract, an agent's tool grants, a hook's blocking rules, the memory layout, the versioning model — and whenever the user says "write an ADR", "document this decision", "why did we do X", "supersede ADR-N", or when the ADR gate blocks a session demanding a decision record. Also use it to supersede or deprecate an existing record, and before any commit that carries a Refs&#58; ADR-NNNN footer.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
metadata:
  version: 1.0.0
  layer: L1-core
---

# ADR Workflow

Decision records are the audit trail for *why* the agent fleet behaves the way it does. Git shows
what changed; the ADR shows what was traded away and what to reconsider when the constraint moves.

Format is **MADR 4.0.0**. Records live in `adr/NNNN-kebab-title.md`.

## When a change needs an ADR

Needs one:
- A skill's contract or trigger surface changes
- An agent's tool grants, model tier or isolation changes
- A hook starts or stops blocking something
- Memory layout, retrieval strategy, or what gets persisted changes
- Versioning, pinning, dependency or release policy changes
- A dependency is adopted or dropped
- Any change that a future reader would ask "why on earth" about

Does not need one:
- Typos, formatting, comment fixes
- Patch-level dependency bumps with no behaviour change
- Implementing something an accepted ADR already decided (reference it instead)

## Create one

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adr_new.py" "Use model2vec for local embeddings"
```

The script allocates the next number, renders the MADR template, and prints the path. It never
overwrites. Then fill it in — the sections below are not optional prose, they are the point.

## The template, and what actually goes in it

Read `reference/madr-4.0.0.md` for the full annotated template. The parts that carry weight:

**Context and Problem Statement** — the forces, in two or three sentences. What is true about the
world that makes this a decision rather than an obvious call. Write it so it still reads clearly in
a year when you have forgotten the session.

**Decision Drivers** — the constraints that actually discriminate between options. "Must be fast"
is not a driver. "Hook budget is 200 ms and Python cold start is ~40 ms" is.

**Considered Options** — at least two, honestly. An ADR with one option is a changelog entry.

**Decision Outcome** — the choice, and the *because*. Then:
- *Consequences* — good and bad. The bad ones are the valuable half. If you cannot name a downside
  you have not understood the trade-off.
- *Confirmation* — how you would know this decision was wrong. A benchmark, an error rate, a
  threshold. This is what turns an ADR into something falsifiable.

**Pros and Cons of the Options** — per option, symmetrical. Do not strawman the rejected ones.

## Status lifecycle

```
proposed ──accept──▶ accepted ──▶ deprecated
                        │
                        └──superseded by ADR-NNNN──▶ superseded
```

Set `status` in the YAML frontmatter. **Accepted records are immutable** — you do not edit the
decision, you supersede it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adr_new.py" "Replace model2vec with MLX embeddings" --supersedes 0007
```

That writes the new record with `supersedes: [0007]` and flips ADR-0007 to
`status: superseded` with `superseded-by: [0012]`. Both files then commit together in one
`docs(adr):` commit — this is the one case where two ADR files share a commit, because the
supersession is a single logical fact.

## Linking to code

Three-way linkage, all of it mechanical:

1. **Commit footer** — `Refs: ADR-0007`
2. **Skill/agent manifest** — `"adr": ["ADR-0007"]` in `skill.json`
3. **The ADR itself** — list the components it governs in the `affects` frontmatter array

The `doctor.py --adr` check verifies that every ADR id referenced from a manifest exists and is not
`superseded` without the manifest pointing at the successor.

## Order of operations

The ADR lands **before** the code it justifies:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adr_new.py" "Gate Stop on uncommitted core logic"
# ... write it, set status: accepted ...
git add adr/0005-gate-stop-on-uncommitted-core-logic.md
git commit -m "docs(adr): add ADR-0005 on gating Stop for uncommitted core logic"
# ... now implement ...
git add plugins/governance-gates/hooks/scripts/commit_adr_gate.py
git commit -m "feat(hook/commit-adr-gate): block Stop on dirty core logic" -m "Refs: ADR-0005"
```

Writing the ADR first is not ceremony. If the Decision Outcome is hard to write, the design is not
finished, and you have just saved yourself the implementation.

## Reviewing the log

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adr_new.py" --list          # index with statuses
grep -rl "status: proposed" adr/                                   # decisions still open
```

Proposed records are debt. Either accept them or delete them.
