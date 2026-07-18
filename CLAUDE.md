# agentic-os — repo development instructions

This repo IS a Claude Code plugin marketplace. It is the single source of truth for
portable agent logic. This file governs working ON the repo (it is not shipped — a
plugin-level CLAUDE.md is ignored by Claude Code; ship instructions as skills).

## Non-negotiables

1. **Atomic commits.** One component (skill/agent/command/hook/manifest) per commit.
   Conventional Commits with a scope: `feat(skill/foo): ...`. See ADR-0004.
2. **Bump SemVer** in the owning `plugin.json` on any shipped plugin change. A stale
   `version` makes updates a silent no-op for installed users.
3. **Pin releases** in `.claude-plugin/marketplace.json` with both `ref` (tag) and
   `sha` (exact commit). `sha` is the real install pin — set it on every release.
4. **ADR for decisions.** New dep / new gate / changed default / new plugin → write a
   MADR record in `adr/` (adr-writer skill) and add `Refs: ADR-XXXX` to the commit footer.
5. **No secrets in git.** MCP configs reference env vars only. Obsidian/REST keys live
   in the environment, never committed.

## Layout

- `plugins/<name>/.claude-plugin/plugin.json` — manifest (name required).
- `plugins/<name>/{agents,skills,commands,hooks}/` — components at plugin root, NOT
  inside `.claude-plugin/` (the #1 mistake that makes a plugin load but do nothing).
- `adr/` — decision records. `memory/` — L2 committed run summaries (durable only).

## Release

`make release PLUGIN=<name> VERSION=X.Y.Z` → validate, changelog, tag, then set the
plugin's `sha` in marketplace.json to the tagged commit.

## Rollback

Default: bump the plugin's `sha`/`ref` in marketplace.json back to the previous release.
Surgical, per-plugin. Alternatively `git revert <sha>` of the one atomic commit.
