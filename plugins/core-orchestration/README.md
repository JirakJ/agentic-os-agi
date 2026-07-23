# core-orchestration

The hub. Every other plugin in this marketplace either depends on it directly or on something
that does: `governance-gates` calls its validator, `self-evolution` evaluates its release tooling,
`long-horizon` and `autonomic-loop` sit on top of all three. This plugin ships no hooks and no
runtime enforcement of its own — it is the authoring and release discipline the rest of the
marketplace is built out of: atomic commits per component, MADR decision records, skill/agent
authoring conventions, and a SemVer release flow with SHA-pinned rollback.

## Components

| Component | Kind | Purpose |
|---|---|---|
| `commands/adr.md` (`/adr`) | command | Allocate a decision-record number and scaffold a MADR file |
| `commands/os-doctor.md` (`/os-doctor`) | command | Run the marketplace validator and report findings |
| `commands/os-release.md` (`/os-release`) | command | Cut a SemVer release of a plugin, or roll one back by re-pinning |
| `agents/adr-writer.md` | agent | Research and draft a decision record for a change that alters behaviour, contracts or policy |
| `agents/release-manager.md` | agent | Cut releases and execute rollbacks across the marketplace |
| `agents/skill-author.md` | agent | Build or rework a skill, subagent, hook or slash command end to end |
| `skills/adr-workflow` | skill | MADR 4.0.0 authoring: when a change needs a record, how to write one that earns its keep |
| `skills/commit-discipline` | skill | Atomic commits, Conventional Commits scoping, ADR footers |
| `skills/release-flow` | skill | Version resolution, SemVer bump derivation, rollback by re-pin |
| `skills/skill-authoring` | skill | Plugin layout, frontmatter, plugin-selection, versioning a change |
| `scripts/adr_new.py` | script | Allocates the next ADR number, scaffolds `adr/NNNN-kebab-title.md` |
| `scripts/doctor.py` | script | Structural/semantic validator: manifests, skill/frontmatter version drift, ADR graph, hook wiring, misfiled components |
| `scripts/release.py` | script | Derives a SemVer bump from Conventional Commits, writes `plugin.json`, regenerates the changelog, tags, re-pins the marketplace entry |

No `hooks/`, no `evals/`. This plugin is pure tooling and conventions, invoked deliberately (a
command, a delegated agent) or read on demand (a skill) — nothing here fires on its own. The hooks
that make its conventions structural (blocking an uncommitted core change, blocking an invalid
manifest) live in `governance-gates`, which depends on this plugin to do the actual validation.

## How this relates to the rest of the marketplace

`core-orchestration` defines the rules; it does not enforce them and it does not measure them.
Three other plugins each take one of those jobs:

| | `core-orchestration` (this plugin) | `governance-gates` | `self-evolution` |
|---|---|---|---|
| Answers | *how* to author, commit, decide, release | *whether* a session may proceed | *whether* the fleet is measurably better or worse |
| Mechanism | conventions + scripts, invoked deliberately | hooks, fire automatically | eval harness + audit-trail miner, invoked deliberately or by `autonomic-loop` |
| Depends on this plugin for | — | `doctor.py` (manifest validity) | `release-plan` eval exercises `release.py`'s dry-run planning |

Concretely: `doctor.py` is what `governance-gates`' `manifest-validator` hook runs after every core
edit, and what `release.py` refuses to release over. `adr_new.py` backs both `/adr` and the
`adr-writer` agent — the same allocator, so a number is never hand-picked or double-issued.
`release.py` backs `/os-release`, the `release-manager` agent, and (dry-run only) the
`self-evolution` capability eval `release-plan`.

## Usage

```
/adr "Title" [--supersedes NNNN]     # scaffold a decision record
/os-doctor [--manifests|--skills|--adr|--hooks]   # validate the marketplace
/os-release <plugin> --dry-run [--bump major|minor|patch]   # plan a release
```

For anything larger than a command — drafting a real ADR, authoring a new component end to end,
cutting or rolling back a release across several plugins — delegate to the matching agent
(`adr-writer`, `skill-author`, `release-manager`) rather than doing the multi-file reading and
writing inline; that is exactly the work these agents exist to keep out of the orchestrator's
context.

Read the `skill-authoring` skill before adding anything to any plugin in this marketplace, and
`commit-discipline` before committing it — both are written for exactly this repo's layout, not
as generic advice.
