---
status: accepted
date: 2026-07-23
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/anti-ai, skill/anti-ai, marketplace]
supersedes: []
superseded-by: []
---

# ADR-0028 — Anti-ai humanization skill replaces self-grading with a deterministic linter

## Context and Problem Statement

The source skill this is carried forward from is a prose-only AI-text-humanization skill: two
validated recipes (discourse fracture, interleave protocol) plus a self-verify step written as
instructions to the model itself — "Count, literally"; "Grep the draft literally for…". A model
asked to count its own em-dashes and significance-markers, then grade whether it passed, is
grading its own homework: the failure mode that produces is not "the recipe doesn't work" (it
does — field-tested 2/2 to 4/4 on fresh topics per the skill's appendix) but "the model reports a
clean checklist over text that still has the tells", because self-report is not verification. Every
countable item on that checklist — a word count, an em-dash tally, a lexicon match, a ratio — is
mechanically checkable by a stdlib script; four items on it (whether the text reads as one
incident vs. an argument, whether a line performs as a punchline, whether coverage of the
original's points was actually cut, whether the ending lands as a genuine contradiction rather
than a moral) are judgment calls no local tool can make, because making them would require
solving the same detection problem the recipes exist to evade.

## Decision Drivers

* Self-grading is the specific, named weakness here, not the recipes — fixing it means replacing
  the grader, not rewriting the recipes that already field-test cleanly
* Roughly half the self-verify checklist (lexicon, em-dashes, constraint-14 significance-markers,
  word count, soft adverbs, burstiness, entity budget, interleave ratio/consecutive-AI-sentences/
  human-opening) is deterministically countable in a few dozen lines of stdlib code; the rest
  (story-test, punchline-test, coverage-test, ending) is not, and pretending otherwise would be a
  false claim of detector-proofness this record explicitly must not make
* ADR-0022 (one gate runtime per concern) already drew the line between "fires automatically" and
  "invoked deliberately" for a reasoning-heavy plugin (`security-gate`); a humanization pass over
  arbitrary drafted prose is authoring assistance requested on demand, not a concern anything
  should gate on every tool call
* The skill is explicit-invocation-only by its own frontmatter (fires on `/anti-ai` or the skill
  named directly, never on paraphrased intent like "humanize this") — whatever ships this in must
  not widen that trigger surface as a side effect of packaging

## Considered Options

* **Fold the skill into an existing plugin** (e.g. `business-ops`' `content-pipeline`, or
  `day-job`). Rejected: this skill ships its own dependency-free Node linter, its own reference
  data (`wordbank.md`, `tells.md`) and its own eval set, none of which relate to invoicing,
  releases or status reports — bundling it would tie its version and rollback to an unrelated
  plugin's release cadence for no shared concern, exactly the "would you roll it back on its own"
  test the plugin-selection rule asks.
* **Ship it prose-only, as the source skill already is** (skip the linter). Rejected — this is not
  an alternative to the decision, it is the problem statement: the self-check stays a hand-count,
  and a model grading its own em-dash count is the exact failure this record exists to close.
* **Run `tellscan.mjs` automatically as a Stop hook** over any AI-authored prose leaving the
  session. Rejected per ADR-0022: this is on-demand authoring help invoked when a user wants a
  specific LinkedIn post or newsletter section rewritten, not a concern with a reliable trigger
  event equivalent to "a commit is about to land" — there is no tool-call shape that reliably means
  "this text is about to be shown to a human as a human's own words," and forcing one would add a
  second always-on runtime for a concern that has never been gated and does not need to be.
* **A standalone plugin, skill unchanged in its recipes, self-verify step redirected to a
  deterministic linter the model runs instead of self-reporting.** Chosen.

## Decision Outcome

Chosen option: ship `anti-ai` as its own plugin, because the skill's actual novel contribution —
`scripts/tellscan.mjs`, a stdlib-only Node linter — is a standalone, versionable unit with no
shared concern with any existing plugin, and packaging it as anything else would either dilute an
unrelated plugin's rollback boundary or quietly re-introduce the self-grading problem this record
exists to remove.

The skill's recipes do not change: discourse fracture and the interleave protocol are unmodified,
empirically field-tested prose instructions. What changes is the self-verify step at the end of
each mode — it now says "run the linter" instead of "count, literally," and the linter
(`node scripts/tellscan.mjs --mode detector <file>`, `--mode reader <file>`, or `--json`) prints
one ✓/✗ line per countable check with the actual count: tier-1 wordbank hits, em-dash count,
constraint-14 significance-marker greps, word count, soft-adverb count, burstiness (short + long
sentence presence), an entity-budget estimate, and — when a human base draft is supplied via
`--human` — the interleave metrics (AI-word ratio, max consecutive AI sentences, human-opening
check). The linter is honest about its own ceiling: it clears the mechanical subset only. The four
irreducibly judgment-based checks (story-test, punchline-test, coverage-test, ending) stay listed
in `SKILL.md` as the model's job, explicitly, every time — a green linter is a floor, not a pass,
and neither the skill, the README, nor the plugin manifest describe it as detector-proof.

### Consequences

* Good, because the mechanical half of verification is now reproducible and cannot be gamed by an
  agent's own self-report — the same linter run against the same file always prints the same
  counts, and `--selftest` gives the linter itself a regression check independent of any live
  detector
* Good, because explicit-invocation-only scope is preserved exactly as the source skill defined
  it — packaging it as a plugin did not, and must not, widen when it fires
* Bad, because mechanization covers only the countable half of the checklist by construction; a
  user who reads "the linter passed" as "this will beat a detector" is drawing a conclusion this
  plugin does not support — mitigated by repeating the floor-not-pass caveat in the skill body,
  the README, and the plugin manifest description, but not eliminated by any of them
* Bad, because the four judgment checks remain exactly as easy to skip under time pressure as they
  were before this change — the linter cannot enforce that they were actually performed, only that
  the mechanical ones were

## More Information

Implemented in `plugins/anti-ai` (`skills/anti-ai/SKILL.md`, `skills/anti-ai/scripts/tellscan.mjs`,
`skills/anti-ai/references/{wordbank,tells}.md`, `skills/anti-ai/evals/evals.json`). Registered in
`.claude-plugin/marketplace.json` under category `writing`. Revisit if statistical detectors
retrain against the countable subset itself (e.g. entity-budget or burstiness stop correlating
with a human verdict) — the fix is updating `wordbank.md`/`tells.md`/the linter's thresholds, not
reintroducing self-grading.
