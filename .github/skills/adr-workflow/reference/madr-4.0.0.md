# MADR 4.0.0 — annotated template

The canonical template, with notes on what each section is actually for. `adr_new.py` renders the
stripped version of this; use this file when you need to know what to write, not just where.

```markdown
---
status: proposed          # proposed | accepted | deprecated | superseded
date: 2026-07-16          # date of the last status change
decision-makers: [Jakub Jirak]
consulted: []             # people/sources whose expertise was sought
informed: []              # people kept up to date
affects: []               # components this governs: skill/vault-recall, hook/secret-guard, ...
supersedes: []            # [0007]
superseded-by: []         # [0012]
---

# ADR-NNNN — Short present-tense title naming the decision

## Context and Problem Statement

Two to four sentences. The forces in play and why this is a decision rather than an obvious call.
Frame it as a question if that helps. Assume the reader has forgotten everything about the session
that produced it.

## Decision Drivers

* Driver that actually discriminates between the options — with a number where one exists
* Constraint imposed from outside (platform, budget, contract)
* Property you refuse to trade away

Not drivers: "should be good", "must be maintainable". If a driver does not rule an option out, cut it.

## Considered Options

* Option 1 — name it the way you would say it out loud
* Option 2
* Option 3

At least two. Honestly.

## Decision Outcome

Chosen option: "Option 2", because <the one sentence that does the work — the driver it satisfies
that the others do not>.

### Consequences

* Good, because <concrete outcome>
* Good, because <concrete outcome>
* Bad, because <the cost you are accepting — this half is the valuable one>
* Bad, because <the door this closes>

### Confirmation

How you would find out this was wrong. A benchmark, an error rate, a threshold, an observation.
"Revisit if p95 recall latency exceeds 150 ms" beats "revisit if it becomes a problem".

## Pros and Cons of the Options

### Option 1

<one line describing it>

* Good, because <argument>
* Neutral, because <argument>
* Bad, because <argument>

### Option 2

...

Symmetrical treatment. Do not strawman the options you rejected — future-you may need to pick one
of them up when a driver changes.

## More Information

Links, benchmarks, prior art, the commit that implemented it, when to revisit.
```

## Frontmatter fields used by tooling

| Field | Read by | Purpose |
|---|---|---|
| `status` | `doctor.py --adr`, ADR gate | lifecycle enforcement; `proposed` records are flagged as debt |
| `affects` | `doctor.py --adr` | reverse index from component → decision |
| `supersedes` / `superseded-by` | `adr_new.py --supersedes` | maintains the supersession chain on both ends |
| `date` | `adr_new.py --list` | ordering in the index |

## Why MADR over Nygard

Nygard's original four-section format (Context / Decision / Status / Consequences) is lighter, and
for a long-lived agent fleet that lightness costs you the two sections that matter most:
*Considered Options* and *Confirmation*. Without options, the record cannot tell you whether a
rejected path is worth revisiting when a driver moves. Without confirmation, the record cannot be
falsified, so it never gets revisited at all. MADR 4.0.0 keeps both and stays plain Markdown with
no tooling lock-in — see ADR-0005.
