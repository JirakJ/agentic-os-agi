---
status: accepted
date: 2026-07-19
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/core-guardrails, manifest/memory-fabric, manifest/business-ops, manifest/day-job]
supersedes: []
superseded-by: []
---

# ADR-0025 — Carried skills get manifests at the version they actually shipped

## Context and Problem Statement

The four plugins carried in from the other lineage brought thirteen skills with no `skill.json`.
`doctor` warned on every one of them:

```
WARN  plugins/<p>/skills/<s>/skill.json
      no skill.json; per-skill version, dependencies and ADR links are unavailable
```

That other lineage versioned in lockstep — one repo-wide `VERSION`, bumped across everything at
once — so its skills never carried individual versions. This repo makes the plugin the unit of
versioning (ADR-0002) and reads per-skill manifests for dependency and ADR linkage, so the gap
is real and not cosmetic: without them, `collect_adr_refs` cannot see which decisions those
thirteen skills implement, and the ADR graph is silently incomplete.

## Decision Drivers

* Thirteen standing warnings train people to skim `doctor` output, which is how a real error
  gets missed
* A manifest that states something false is worse than a missing manifest
* The ADR graph is only useful if it is complete — a skill with no recorded decisions is
  indistinguishable from a skill nobody linked up

## Considered Options

* **Leave the warnings.** Honest, but permanently noisy, and leaves the ADR graph incomplete.
* **Start every carried skill at 1.0.0.** Reads as "new", which is false — this code has been
  in production use through three major cycles of its plugin.
* **Version each skill at the plugin version it shipped in.** Chosen.

## Decision Outcome

All thirteen get a `skill.json` at **3.0.0**, matching the plugin version they shipped in, with
`stability: stable` — they have been running in production, and claiming `experimental` would be
as false as claiming they are new. `metadata.version` is added to each `SKILL.md` frontmatter to
match, because `doctor` treats a manifest/frontmatter mismatch as an error rather than a warning.

`adr` links are populated only where a real decision governs the skill:

| Skill(s) | Linked |
| --- | --- |
| `memory-capture`, `memory-compact`, `memory-retro` | ADR-0019, ADR-0021 |
| `obsidian` | ADR-0019 |
| `guardrail-forge` | ADR-0022 |
| `copilot-rollout-ops` | ADR-0016, ADR-0018 |
| the rest | *empty* |

Empty is deliberate. `business-ops` and `day-job` are operational playbooks that implement no
architectural decision of this OS, and inventing a plausible-looking link to pad the graph
would corrupt exactly the thing the graph is for.

### Consequences

Good: `doctor` is clean at 73 components, so the next warning that appears is signal. The ADR
graph now reaches the carried skills.

Bad: 3.0.0 is inherited from a lockstep scheme this repo has abandoned, so those thirteen start
their independent life at a version number that means nothing on its own — the first genuine
change to any of them will bump it into a per-skill series that shares no history with the
plugin's. That is the price of not lying about their provenance, and it resolves itself after
one release of each.
