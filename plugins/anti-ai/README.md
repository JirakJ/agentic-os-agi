# anti-ai

Explicit-invocation AI-text-humanization skill: two field-tested recipes (discourse fracture,
interleave protocol) carried over unmodified from the source skill, plus a deterministic linter,
`scripts/tellscan.mjs`, that replaces the hand-count the source skill used to verify itself. See
[ADR-0028](../../adr/0028-anti-ai-humanization-skill-replaces-self-grading-with-a-deterministic-linter.md).

## What this is, and what it is not

This is not a detector, and it does not claim to beat one. `tellscan.mjs` is a stdlib Node script
that counts the countable half of the skill's own self-check — it cannot predict a real
statistical detector's verdict, no local tool can, and neither the skill nor this README says
otherwise. A green linter run is a floor under the mechanical subset of the checklist, not a pass
on the whole thing.

## The linter is the differentiator

The recipes themselves — discourse fracture (for AI-only source text) and the interleave protocol
(for when a human base draft exists) — are unchanged, empirically validated prose instructions;
`SKILL.md` carries the full evidence base. What changed is the verification step. The source
skill's self-check was written as instructions to the model: "Count, literally"; "Grep the draft
literally for…" — a model grading its own output on whether it followed its own instructions is
exactly the failure mode that survives no matter how good the instructions are. `tellscan.mjs`
replaces the hand-count with a run of actual code:

```bash
node skills/anti-ai/scripts/tellscan.mjs --mode detector path/to/draft.txt
```

It prints one checked line per countable item, with the real count next to it: tier-1 wordbank
hits, em-dash count, constraint-14 significance-marker greps ("thats the part that got me" and
its siblings — the single cleanest kill in the evidence base), word count, soft-adverb count,
burstiness (short- and long-sentence presence), and an entity-budget estimate. When a human base
draft exists (the reliable variant of the recipe), pass it in for the interleave metrics:

```bash
node skills/anti-ai/scripts/tellscan.mjs --mode detector --human draft.txt rewrite.txt
```

which adds `ai_word_ratio` (must stay under ~0.40), `max_consecutive_ai_sentences` (must be under
2) and `opening_is_human` — three numbers that used to be pure vibes and are now counted.
`--mode reader` runs the reader-facing audit instead (tier-1/tier-2 lexicon, em-dashes,
rhetorical-Q&A and negative-parallelism greps, burstiness); `--json <file>` emits raw metrics for
scripting; stdin works via `-`; `--selftest` runs the linter's own regression fixtures — the same
one this plugin's build was verified against.

**What the linter cannot check, and does not pretend to:** whether the text reads as one
meandering incident rather than a restructured argument (the story-test), whether a line performs
as a punchline, whether the rewrite actually dropped most of the source's points rather than
translating all of them into story beats (the coverage-test), and whether the ending lands as a
genuine self-contradiction rather than a moral. `SKILL.md` lists those four explicitly, every
time, as the model's job after the linter is green — because making a local tool judge them would
require solving the same detection problem the recipes exist to evade.

## How this relates to the rest of the OS

`anti-ai` is a standalone plugin with no declared dependencies — it does not sit in the
`core-orchestration → governance-gates → self-evolution → long-horizon → autonomic-loop` chain,
and nothing in that chain depends on it. It is also not part of the three-layer memory stack
(ADR-0003): it neither reads nor writes vault or index state, it transforms text handed to it in
the same turn and returns a rewrite. Install it on its own.

It ships **no hooks, no `mcpServers`, no `permissionMode`** — nothing here fires on its own. The
skill is explicit-invocation-only by its own frontmatter: it fires on `/anti-ai`, or when the user
literally writes "anti-ai" / "use the anti-ai skill". It deliberately does **not** fire on
paraphrased intent — "humanize this," "make it sound less AI," "this reads like ChatGPT" get
handled as an ordinary rewrite unless the skill is named, per the skill's own scoping. A `Stop`
hook that ran the linter automatically over any AI-authored prose leaving a session was
considered and rejected (ADR-0028, per ADR-0022's one-gate-runtime-per-concern rule): this is
on-demand authoring help requested for a specific piece of text, not a concern with a reliable
gate-worthy trigger event the way a commit or a tool call is.

## Components

- `skills/anti-ai/SKILL.md` — mode selection (reader vs. detector), the two recipes, and the
  self-verify steps that now point at the linter instead of a hand-count.
- `skills/anti-ai/scripts/tellscan.mjs` — the linter. Stdlib-only Node, zero dependencies,
  `--selftest` included.
- `skills/anti-ai/references/wordbank.md`, `references/tells.md` — the lexicon tiers and AI-tell
  constructions the linter's checks and `SKILL.md`'s reader-mode pass both draw on.
- `skills/anti-ai/evals/evals.json` — three worked prompts (LinkedIn post, blog intro, newsletter
  anecdote) with expected-output criteria, consumable by the `self-evolution` capability harness
  if that plugin is also installed.

No `hooks/`, no `agents/`, no `commands/`. The skill is the entire plugin.
