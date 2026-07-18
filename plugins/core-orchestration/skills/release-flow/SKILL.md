---
name: release-flow
description: Cut and roll back versioned releases of agentic OS plugins — SemVer bumps, git-cliff changelogs, per-plugin tags, GitHub releases and SHA pinning in the marketplace catalog. Use this whenever the user says "release", "cut a version", "tag it", "ship it", "publish the plugin", "bump the version", or asks to roll back, revert or downgrade a plugin, skill or agent to a previous version. Also use it after finishing a feature or phase, when a release breaks something and needs reverting, and when deciding whether a change is major, minor or patch.
allowed-tools: Bash, Read, Edit, Grep, Glob
metadata:
  version: 1.0.0
  layer: L1-core
---

# Release & Rollback

The plugin is the unit of versioning, distribution and rollback. Individual skills carry versions
for the toolchain's benefit, but what installs, updates and reverts is a plugin.

## Version resolution — know which one wins

Claude Code resolves a plugin's version from the first of:

1. `version` in `plugins/<p>/.claude-plugin/plugin.json`
2. `version` in the marketplace entry
3. the git commit SHA

**Never set `version` in both.** `plugin.json` wins silently and the marketplace value becomes a
lie that nothing warns you about. This repo sets it in `plugin.json` only; the marketplace entry
carries `source` + `sha`.

## Cut a release

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" <plugin> --bump minor
```

The script, in order:

1. refuses if the tree is dirty or `doctor.py` fails
2. derives the bump from Conventional Commits since the last tag when `--bump` is omitted
   (`feat` → minor, `fix`/`perf`/`refactor` → patch, `!`/`BREAKING CHANGE` → major)
3. writes `version` into `plugin.json`
4. regenerates `plugins/<p>/CHANGELOG.md` via git-cliff, scoped with `--include-path`
5. commits `chore(manifest/<plugin>): release vX.Y.Z`
6. tags `<plugin>/vX.Y.Z`
7. rewrites the plugin's `sha` in `.claude-plugin/marketplace.json` to the tagged commit and
   commits that as `chore(marketplace): pin <plugin> to vX.Y.Z`

`--dry-run` prints the plan and touches nothing. Use it first, every time.

Pushing tags is what triggers the GitHub release workflow:

```bash
git push origin main --follow-tags
```

## Why the marketplace is SHA-pinned

Each entry carries both `ref` (the tag, human-readable) and `sha` (the exact commit). The `sha` is
the effective pin: installs resolve to that commit even if the branch moves or is deleted, which is
what makes a rollback deterministic rather than hopeful. This mirrors how Anthropic's own
submission pipeline pins approved plugins.

## Rollback — three levers, in order of preference

### 1. Re-pin the marketplace entry (surgical, preferred)

Roll back one plugin, leave everything else on latest:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" memory-obsidian --pin v1.1.0
git push
```

Rewrites that entry's `sha`/`ref` to the older tag. Next session start, the plugin resolves to the
old code. Nothing else in the fleet moves. No history is rewritten.

### 2. Revert the offending commit (fixes the source, not just the pin)

Because commits are atomic per component, one revert restores one component:

```bash
git log --oneline -- plugins/memory-obsidian/skills/vault-recall/
git revert <sha>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" memory-obsidian --bump patch
```

Revert, do not `git checkout` a subtree — a revert is itself a commit, so the audit trail survives
and the ADR trail still explains why.

Reverting a change that an accepted ADR justified means that ADR is now wrong. Supersede it in the
same turn; a revert with no decision record is how the same mistake gets made twice.

### 3. Channels (fleet-wide)

Maintain a `stable` branch alongside `main` and point managed settings at it. Roll the whole fleet
back by moving the branch. Only worth the overhead once more than one machine consumes the
marketplace.

## Choosing the bump

| Change | Bump |
|---|---|
| New skill, new agent, new command, broader trigger surface | minor |
| Bug fix, tightened prose, faster script, same contract | patch |
| Skill or agent removed or renamed; output shape changed; tools narrowed; hook starts blocking what it allowed | **major** |

A hook that starts blocking something is a breaking change even though no interface moved — it
changes what the system permits. Treat governance changes as contract changes.

Pre-1.0 plugins may break on minor. Once a plugin has left your machine, honour SemVer strictly.

## Changelog

git-cliff (`brew install git-cliff`) reads Conventional Commits and renders `CHANGELOG.md`. Config
lives in `cliff.toml` at the repo root; per-plugin scoping is `--include-path plugins/<p>/**`.

This is exactly why commit hygiene is enforced upstream: the changelog is a *derived artifact*. A
sloppy commit message is a sloppy release note, permanently.

## Release checklist

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"                    # everything green
git status --porcelain                                                # clean
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" <plugin> --dry-run # read the plan
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" <plugin> --bump <level>
git push origin main --follow-tags
```

Then verify the consumer side:

```bash
claude plugin update <plugin>
claude plugin list
```

## Dependencies between plugins

`plugin.json` takes a native `dependencies` map with SemVer ranges. When several installed plugins
constrain the same dependency, Claude Code intersects the ranges and resolves to the highest
version satisfying all of them; an unsatisfiable set disables the plugin with
`dependency-version-unsatisfied`. So a major bump on `core-orchestration` breaks
`governance-gates` (which requires `^1.0.0`) until its range is widened — bump both, in separate
commits, in the same release.

`claude plugin prune` drops orphaned auto-installed dependencies. Cross-marketplace dependencies
need an `allowCrossMarketplaceDependenciesOn` allowlist in `marketplace.json`; this repo keeps all
three plugins in one marketplace precisely to avoid that.
