# Changelog

Derived from Conventional Commits by git-cliff. Do not edit by hand.

## 0.1.0 — 2026-07-23

### Features

- **anti-ai**: Add the explicit-invocation AI-text-humanization skill (ADR-0028) — discourse
  fracture and interleave-protocol recipes, unchanged from the source skill, plus
  `scripts/tellscan.mjs`, a stdlib Node linter that machine-verifies the mechanical subset of the
  self-check (tier-1 wordbank hits, em-dashes, constraint-14 significance-markers, word count,
  soft adverbs, burstiness, entity budget, and interleave ratio/consecutive-AI-sentence/human-
  opening) instead of a hand-count. The four judgment calls (story-test, punchline-test,
  coverage-test, ending) stay the model's job by design; a green linter is a floor, never a
  detector-proof claim. Ships no hooks; fires only on explicit invocation.
