---
name: skill-authoring
description: Author and modify Claude Code skills, subagents, hooks and slash commands inside the agentic OS marketplace, following its layout, frontmatter and versioning conventions. Use this whenever the user asks to create, add, change, split, rename or delete a skill, subagent, hook or slash command, whenever they say "make a skill for X", "add an agent that Y", "this skill should also Z", or whenever a manifest validator rejects a component. Also use it when deciding which plugin a new component belongs in, or when a skill has grown too large and needs progressive disclosure.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
metadata:
  version: 1.0.0
  layer: L1-core
---

# Skill & Component Authoring

The conventions that make components in this marketplace loadable, versioned and rollback-safe.

## Where things live

```
plugins/<plugin>/
├── .claude-plugin/plugin.json   # ONLY the manifest lives in the hidden dir
├── skills/<name>/SKILL.md       # everything else sits at the plugin root
├── skills/<name>/skill.json
├── skills/<name>/reference/
├── agents/<name>.md
├── commands/<name>.md
├── hooks/hooks.json
├── hooks/scripts/
└── scripts/
```

**The single most common failure**: putting `skills/`, `agents/`, `commands/` or `hooks/` *inside*
`.claude-plugin/`. The plugin loads, reports no errors, and does nothing. Only `plugin.json` is
hidden; every component directory is at the plugin root.

Second failure: referencing files outside the plugin directory. Install copies the plugin dir to a
cache, so `../shared/foo.py` resolves to nothing on someone else's machine. Symlink instead, or
duplicate.

Third: a plugin-level `CLAUDE.md` is ignored by the loader. Instructions ship as skills.

## Which plugin does it belong in

| Concern | Plugin |
|---|---|
| How you author, commit, decide, release | `core-orchestration` |
| Something that blocks, validates or records | `governance-gates` |
| Something that reads, writes or retrieves knowledge | `memory-obsidian` |

If a component fits two, it belongs in the one whose *failure* would matter more. When none fit,
that is a new plugin — a new plugin is also a new unit of versioning and rollback, so create one
only when you would genuinely want to roll it back independently.

## SKILL.md frontmatter

```yaml
---
name: vault-recall              # must equal the directory name; lower-case, hyphens
description: <trigger surface>  # the single field that decides whether the skill fires
allowed-tools: Bash, Read       # narrow it; omit to inherit everything
context: fork                   # optional: run in a forked context, return only the result
metadata:
  version: 1.0.0                # convention, not runtime-enforced — mirror it in skill.json
  layer: L1-core                # L1-core | L2-episodic | L3-knowledge | L4-index
---
```

`name` and `description` are the only required fields.

### The description is the product

It is the whole triggering mechanism and it is always in context. Claude undertriggers skills by
default, so write it *pushy* and concrete:

- Say what the skill does **and** enumerate the phrasings and situations that should fire it
- Include the words a user would actually type, including the vague ones
- Include the failure modes that should route here ("when the validator rejects a manifest")
- All "when to use" content belongs here, never in the body

Weak: `Retrieves notes from the vault.`
Strong: `Retrieve relevant notes from the Obsidian vault using hybrid BM25 + vector search. Use whenever the user asks what they previously wrote, decided or captured, says "what do I know about X", "did I write anything on Y", "check my notes", "recall", or references past work without giving the detail — and before answering any question that prior notes would sharpen.`

### Body

Under ~500 lines. Structure for progressive disclosure:

1. **Metadata** (name + description) — always in context
2. **SKILL.md body** — loaded when the skill fires
3. **`reference/*.md`, `scripts/*`** — loaded or executed only on demand

Past ~500 lines, push detail into `reference/` and leave a pointer saying exactly when to read it.
Reference files over ~300 lines get a table of contents.

Write for a competent operator, not a beginner. Imperative, dense, no throat-clearing. Where
determinism matters, ship a script and tell the skill to run it rather than describing the
algorithm in prose — scripts execute without consuming context.

Use `${CLAUDE_PLUGIN_ROOT}` for every path you reference. Never hardcode.

## skill.json

Runtime ignores it; the toolchain does not. It is what gives you per-skill versions, dependency
edges and ADR linkage:

```json
{
  "name": "vault-recall",
  "version": "1.2.0",
  "description": "…",
  "layer": "L4-index",
  "dependencies": { "vault-capture": "^1.0.0" },
  "adr": ["ADR-0003", "ADR-0007"],
  "stability": "stable"
}
```

`stability` is `experimental | stable | deprecated`. Keep `version` in sync with
`metadata.version` in the frontmatter — `doctor.py --skills` fails the build if they drift.

## Subagents

```yaml
---
name: release-manager
description: <when the orchestrator should delegate to this agent>
tools: Bash, Read, Grep, Glob     # grant the minimum; omit to inherit all
model: sonnet                     # sonnet | opus | haiku | inherit
skills: [commit-discipline]       # preloads skill content into the agent's context
---
```

Then the system prompt as the body.

Plugin-shipped agents may **not** declare `hooks`, `mcpServers` or `permissionMode` — the loader
rejects those for security. Project agents win over plugin agents on a name collision.

Reach for an agent, not a skill, when the work needs its own context window: long searches,
multi-file refactors, anything whose intermediate output would otherwise pollute the main thread.

## Slash commands

`commands/<name>.md` — frontmatter `description` and `argument-hint`, body is the prompt. `$1`,
`$2`, `$ARGUMENTS` interpolate. Commands are for things *you* invoke deliberately; skills are for
things Claude should notice on its own. If you find yourself writing a command nobody will
remember to type, make it a skill.

## Versioning a change

| Change | Bump |
|---|---|
| Trigger surface broadens, new capability, new script | minor |
| Wording, typo, tightened prose, same contract | patch |
| Contract changes, output shape changes, tools narrowed, skill removed | **major** |

Bump `skill.json`, `metadata.version`, and the plugin's `plugin.json` in the same turn — but as
separate commits per `commit-discipline`. A stale `plugin.json` version means installed copies
never update: the loader compares versions, and an unchanged version is a no-op.

## Before you commit

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"        # full check
claude plugin validate ./plugins/<plugin>                 # loader's own view
```

`doctor.py` checks manifest schema, name/directory agreement, version drift between `skill.json`
and frontmatter, SemVer well-formedness, dangling ADR references, hook script executability, and
components misfiled under `.claude-plugin/`.

## Hot reload

`SKILL.md` edits are picked up live — save and the next invocation sees them. Everything else
(`hooks.json`, `plugin.json`, agents, commands) needs `/reload-plugins` or a restart. When a change
appears to do nothing, this is why.
