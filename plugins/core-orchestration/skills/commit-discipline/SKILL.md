---
name: commit-discipline
description: Atomic commit discipline for the agentic OS core — one core-logic change per commit, Conventional Commits with component scopes, ADR references in footers. Use this whenever you create, edit, rename or delete a skill, subagent, hook, slash command, plugin manifest or CLAUDE.md instruction, whenever the user says "commit this", "commit the skill", "commit the agent", or whenever a governance gate blocks a session with an uncommitted-core-change error. Also use it before cutting a release, when squashing or splitting commits, and when writing any commit message in this repository.
allowed-tools: Bash, Read, Grep, Glob
metadata:
  version: 1.0.0
  layer: L1-core
---

# Commit Discipline

Every change to core logic is one commit. That is the whole contract, and it is what makes
per-component rollback possible: `git revert <sha>` restores exactly one skill, agent or hook
without touching anything else.

## What counts as core logic

| Path pattern | Component |
|---|---|
| `plugins/*/skills/*/SKILL.md`, `plugins/*/skills/*/skill.json` | skill |
| `plugins/*/agents/*.md` | agent |
| `plugins/*/hooks/**` | hook |
| `plugins/*/commands/*.md` | command |
| `plugins/*/.claude-plugin/plugin.json` | manifest |
| `.claude-plugin/marketplace.json` | marketplace |
| `CLAUDE.md`, `**/CLAUDE.md` | instruction |
| `adr/*.md` | decision record |

Anything else (docs, CI, scripts that are not hooks) follows normal commit hygiene but is not
gated.

## The rule

**One component per commit.** If you edited `commit-discipline/SKILL.md` and `adr-writer.md` in
the same turn, that is two commits. Stage by path, never `git add -A`:

```bash
git add plugins/core-orchestration/skills/commit-discipline/SKILL.md
git commit -m "feat(skill/commit-discipline): enforce path-scoped staging" -m "Refs: ADR-0002"
```

The one exception: a skill's `SKILL.md`, its `skill.json` and its `reference/` files are a single
component and commit together.

## Message format

Conventional Commits with a `type(component/name)` scope:

```
feat(skill/vault-recall): add BM25 prefilter before vector rerank
fix(hook/secret-guard): stop matching .env.example
refactor(agent/release-manager): drop redundant tool grants
docs(adr): add ADR-0007 on local embedding backend
chore(manifest/memory-obsidian): bump to 1.1.0
```

Allowed types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `revert`.
Scopes: `skill/<name>`, `agent/<name>`, `hook/<name>`, `command/<name>`, `manifest/<plugin>`,
`marketplace`, `instruction`, `adr`.

Subject: imperative, lower-case, no trailing period, ≤ 72 chars.

**Breaking changes** — a skill's contract changing, an agent's tool grants narrowing, a hook
starting to block what it used to allow — take a `!` and a footer:

```
feat(skill/vault-recall)!: return snippets instead of full notes

BREAKING CHANGE: callers that parsed the full-note payload must switch to `snippets[]`.
Refs: ADR-0009
```

## ADR footers

Any commit that changes *why* the system behaves the way it does carries a decision record:

```
Refs: ADR-0007
```

If the change is mechanical (typo, formatting, dependency bump) no ADR is needed. If it changes
behaviour, contracts, or policy, write the ADR first — use the `adr-workflow` skill — and commit
the ADR in its own `docs(adr):` commit *before* the change that implements it. The ADR gate
enforces this and will block the session otherwise.

## Ordering within a turn

When a turn touches several components, commit in dependency order so every commit leaves the
tree working:

1. `docs(adr):` — the decision
2. `feat(skill|agent|hook):` — the implementation
3. `chore(manifest/*):` — the version bump
4. `chore(marketplace):` — the SHA/ref pin, only at release time

## Verifying before you commit

```bash
git status --porcelain          # exactly the paths you intend, nothing else
git diff --cached --stat        # one component
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --manifests   # manifests still valid
```

## What never gets committed

- `.index/`, `*.db`, `*.sqlite3` — derived retrieval caches, rebuildable
- `audit/*.jsonl` — runtime audit trail, lives in `${CLAUDE_PLUGIN_DATA}`
- Anything under the Obsidian vault — that is a separate repository (see ADR-0004)
- Secrets in any form. The secret guard blocks reads, but staging is on you.

## Recovering from a blocked session

The `commit-adr-gate` hook blocks `Stop` when core logic is dirty. It prints the offending paths.
Do not disable the hook — commit properly:

```bash
git status --porcelain -- 'plugins/**' 'adr/**' 'CLAUDE.md'
# for each component, in order:
git add <one component's paths>
git commit -m "<type>(<scope>): <subject>"
```

If the change was exploratory and you want it gone: `git checkout -- <paths>`.
