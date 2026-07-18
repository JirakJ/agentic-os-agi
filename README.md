# Agentic OS

A Git-native orchestration layer for [Claude Code](https://docs.claude.com/en/docs/claude-code):
versioned agents, skills and instructions, hook-enforced governance, MADR decision records, a
three-layer memory stack, and a verification-gated self-improvement loop — built entirely from
Claude Code primitives, with no direct LLM API calls.

The premise: your agent fleet's behaviour is text, that text changes constantly, and every change
should be attributable to a diff and revertible in isolation. Git is the source of truth; hooks
make the discipline structural rather than aspirational; decision records capture *why*; capability
evals make change measurable so the system can improve itself without walking into degradation. What
you get is an agent layer you can roll back one component at a time, audit after the fact, and let
compound capability under governance.

## What's in it

Three plugins, each independently versioned and installable:

| Plugin | What it does |
|---|---|
| **core-orchestration** | Authoring and release discipline — atomic commits per component, MADR decision records, skill/agent conventions, SemVer release flow with SHA-pinned rollback. Ships `doctor.py`, `adr_new.py`, `release.py`. |
| **governance-gates** | Hook-enforced quality gates — a secret guard, manifest/SemVer validation, atomic-commit and ADR enforcement at turn's end, and an append-only audit trail of every tool call. Pure-Python hooks, zero dependencies. |
| **memory-obsidian** | Three-layer memory — an Obsidian vault as the knowledge base, a local SQLite FTS5 + sqlite-vec hybrid retrieval index, and durable session memory. Recall returns snippets, not whole notes. |
| **self-evolution** | A verification-gated self-improvement loop — a capability-eval harness with regression tracking, an experience miner over the audit trail, and a proposal engine that turns recurring patterns into governed capability proposals. Ships `evalctl.py`, `mine.py`, `propose.py`. |

Twelve skills, four subagents, eight slash commands, six hooks, ten decision records — all
validated, all tested end-to-end against real payloads and a real git repo.

## Install

```bash
git clone https://github.com/jakubjirak/agentic-os.git
cd agentic-os

# register the marketplace with Claude Code
claude plugin marketplace add .

# install the plugins you want
claude plugin install core-orchestration@agentic-os
claude plugin install governance-gates@agentic-os
claude plugin install memory-obsidian@agentic-os
claude plugin install self-evolution@agentic-os
```

`governance-gates` depends on `core-orchestration` (it calls `doctor.py`); `self-evolution` depends
on both (it evaluates the release tooling and mines the audit trail). Claude Code resolves and
installs dependencies automatically.

Verify the install:

```bash
/os-doctor          # validate every component
/plugin list        # confirm all three are active
```

## Configure memory (optional)

`memory-obsidian` works against your Obsidian vault. Point it at one:

```bash
export AGENTIC_OS_VAULT="$HOME/Documents/Vault"       # your vault
export OBSIDIAN_API_KEY="…"                            # from the Local REST API plugin
```

Then build the index and query it:

```bash
/vault-index --rebuild
/recall "what did I decide about X"
```

The vector arm needs a local embedding model (`pip install sqlite-vec model2vec`). Without it,
recall runs on BM25 alone — fully functional, just without semantic matching. Nothing else is
required; the index is derived data and rebuilds from the vault on demand.

## How it fits together

```
┌─ Git (this repo) ──────────────────────────── L1: core logic, versioned, rollback-able
│   skills · agents · hooks · commands · ADRs
│
├─ governance-gates (hooks) ─────────────────── enforce atomic commits + ADRs + secret hygiene
│   PreToolUse · PostToolUse · Stop · SubagentStop
│
├─ memory/ (Git) ───────────────────────────── L2: durable episodic memory
├─ Obsidian vault (separate repo) ───────────── L3: knowledge base, Obsidian Git
└─ SQLite FTS5 + sqlite-vec (rebuildable) ───── L4: hybrid retrieval index
```

The design decisions behind each layer are in [`adr/`](adr/) — start with
[ADR-0001](adr/0001-git-as-single-source-of-truth-for-core-logic.md) (why Git owns core logic and
Obsidian owns knowledge) and [ADR-0002](adr/0002-plugin-as-the-unit-of-versioning-and-rollback.md)
(why the plugin is the unit of rollback).

## The self-improvement loop

`self-evolution` closes a loop the other three plugins make safe: **sense → reflect → propose →
verify → adopt**. It mines the audit trail (governance's experience buffer) for recurring
workflows, failures and couplings, fuses them with eval regressions, and produces ranked capability
proposals — which the `skill-author` agent implements, `evalctl.py` verifies against a baseline, and
governance adopts through a normal ADR and atomic commit.

```bash
/evals              # run the capability suite; a drop below baseline is a revert signal
/evolve             # mine experience and generate ranked capability proposals
```

The ordering is deliberate and non-negotiable (ADR-0008): verification exists *before*
self-authoring, because a system that modifies itself without measuring the result is taking a
random walk. And the loop proposes rather than auto-merges (ADR-0010) — the one irreversible step,
modifying core logic, always has a gate. This is the governance layer paying off: ADRs justify
self-modifications, atomic commits make them individually revertible, and the audit trail is the
raw material the loop learns from.

## Working in the repo

```bash
make doctor         # validate everything
make test           # run the full suite (hooks + retrieval, real behaviour)
make status         # version/tag/pin drift across plugins
make adr T='Title'  # new decision record
make release P=core-orchestration B=minor   # cut a release (dry-run first, then confirms)
```

Every change to core logic is one commit (`git revert` restores exactly one component), behavioural
changes carry a decision record, and the governance gates enforce both at turn's end. If that
sounds strict — it is, and it is what makes the rollback story real. The rules, and how to work with
them rather than around them, are in the `commit-discipline`, `adr-workflow` and `governance-policy`
skills.

## Design principles

- **Git is the source of truth.** Core logic lives in version control; everything derived (the
  retrieval index, the audit trail) is rebuildable and gitignored.
- **The plugin is the unit of rollback.** SHA-pinned marketplace entries make a rollback one line,
  moving one plugin without disturbing the rest.
- **Governance is structural.** Hooks enforce the discipline the rollback story depends on, so it
  cannot decay when attention lapses.
- **Decisions are recorded.** MADR records capture what was traded away, so a choice can be
  revisited when its drivers move — not re-litigated from scratch.
- **No LLM API calls.** Everything runs inside Claude Code, on its primitives. Embeddings are local
  or absent; the system degrades gracefully, never hard-fails.
- **Zero-dependency hooks.** Python stdlib only, so a fresh clone runs the gates with no install
  step.

## Requirements

- Claude Code with plugin support
- Python 3.12+ (hooks and tooling; stdlib only)
- git, and [git-cliff](https://git-cliff.org) for changelog generation at release time
- Optional: Obsidian + [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api)
  plugin for L3; `sqlite-vec` + `model2vec` for the vector arm of L4

## License

MIT © [Jakub Jirák](https://jakubjirak.com)
