# Agentic OS AGI

A Git-native orchestration layer for [Claude Code](https://docs.claude.com/en/docs/claude-code)
and GitHub Copilot: versioned agents, skills and instructions, hook-enforced governance, MADR
decision records, a layered memory stack, a verification-gated self-improvement loop,
long-horizon autonomy — durable missions, an evidence-derived self-model and a learning
frontier — an autonomic layer that makes the whole loop self-triggering through hooks, plus
commit-integrity guardrails and business/day-job operations. Built entirely from Claude Code
primitives, with no direct LLM API calls.

> **This repo is a merge of two independent lineages** (`agentic-os` and `jj-agentic-os`,
> which shared zero commits). Where they contradicted each other, the conflict is resolved in
> a decision record rather than by whichever hook happened to run last:
> [ADR-0021](adr/0021-one-memory-model-hooks-enqueue-humans-curate.md) (two memory
> philosophies), [ADR-0022](adr/0022-single-gate-runtime-per-concern.md) (two gate runtimes),
> [ADR-0023](adr/0023-the-full-distribution-does-not-fit-a-200k-listing-budget.md) (the merged
> skill listing outgrew its context budget).

The premise: your agent fleet's behaviour is text, that text changes constantly, and every change
should be attributable to a diff and revertible in isolation. Git is the source of truth; hooks
make the discipline structural rather than aspirational; decision records capture *why*; capability
evals make change measurable so the system can improve itself without walking into degradation. What
you get is an agent layer you can roll back one component at a time, audit after the fact, and let
compound capability under governance.

## What's in it

Eleven plugins, each independently versioned and installable (ADR-0002). Nobody installs all
of them — see ADR-0023 for what fits which context window.

| Plugin | What it does |
|---|---|
| **core-orchestration** | Authoring and release discipline — atomic commits per component, MADR decision records, skill/agent conventions, SemVer release flow with SHA-pinned rollback. Ships `doctor.py`, `adr_new.py`, `release.py`. |
| **governance-gates** | Hook-enforced quality gates — a secret guard, manifest/SemVer validation, atomic-commit and ADR enforcement at turn's end, and an append-only audit trail of every tool call. Pure-Python hooks, zero dependencies. |
| **memory-obsidian** | Three-layer memory — an Obsidian vault as the knowledge base, a local SQLite FTS5 + sqlite-vec hybrid retrieval index, and durable session memory. Recall returns snippets, not whole notes. |
| **self-evolution** | A verification-gated self-improvement loop — a capability-eval harness with regression tracking, an experience miner over the audit trail, and a proposal engine that turns recurring patterns into governed capability proposals. Ships `evalctl.py`, `mine.py`, `propose.py`. |
| **long-horizon** | Long-horizon autonomy — durable missions that outlive sessions with structural resumability at session start, an evidence-derived capability self-model, and a learning frontier ordering what to learn next. Ships `mission.py`, `selfmodel.py`, `frontier.py`. |
| **autonomic-loop** | The autonomic nervous system — hook-driven policy that makes the loop self-triggering: core changes are verified before a turn may end (blocking on regression), sessions end by staging mined proposals, sessions start knowing the system's state. Kill-switchable. Ships `autonomic.py`. |
| **core-guardrails** | The gate runtime (ADR-0022) — numbered hook dispatch with enforcing/advisory modes, telemetry and a `/gate-unlock` override: security gate, commit-integrity attestation, no-placeholder, ship lockstep, test gate, context-budget guard. |
| **memory-fabric** | The memory writer — crash-safe queue-based capture into a git-synced Obsidian vault, plus retro and compaction skills. Reads pair with `memory-obsidian`'s index (ADR-0021). |
| **business-ops** | Solopreneur operations — content pipeline, consulting invoicing, JetBrains plugin releases, product launches. |
| **day-job** | Enterprise operations — weekly status reports, Copilot rollout ops, meeting notes to actions. |

Around thirty skills, subagents, slash commands and hook scripts across nine events,
twenty-three decision records and the capability eval suite — validated end-to-end against
real payloads and a real git repo. The OS runs natively on Claude Code and, via generated
adapters (`scripts/build-adapters.py`, ADR-0016), on GitHub Copilot surfaces.

## Default set

Nobody should install all twelve plugins by default: every installed skill's `name` +
`description` is charged against the always-on skill-listing budget of *every* session, before any
work happens. ADR-0023 measured the full distribution against a 200k-context listing budget and
refused to weaken the gate to make a bigger merge look clean; ADR-0024 fixed the gate to measure
what a machine actually has installed rather than the whole repository, falling back to the full
distribution only when it cannot tell what is installed at all. `scripts/skill-budget-lint.py` is
the enforcement — see both records before changing what it measures or its threshold.

On this machine, the enabled set is:

- `core-orchestration` — the authoring/release hub; nearly everything else depends on it
- `core-guardrails` — the gate runtime (ADR-0022)
- `memory-fabric` — the memory writer (ADR-0021)
- `business-ops` — solopreneur operations
- `day-job` — enterprise operations
- `security-gate` — on-demand AI security review (ADR-0026)

Opt-in — install deliberately, per context budget and need, not by default:

- `governance-gates`, `self-evolution`, `long-horizon`, `autonomic-loop` — the self-improvement
  and long-horizon autonomy stack. Each depends on the last (`autonomic-loop` → `long-horizon` →
  `self-evolution` → `governance-gates` → `core-orchestration`), so installing the outermost one
  pulls the rest in automatically; install only as far down the chain as the work needs.
- `memory-obsidian` — the vault-backed retrieval layer (L3 read + L4 index). No declared
  dependencies; install it independently of the stack above.
- `proto-forge` — the prototype-generation workflow — ships from its own marketplace
  (`/plugin marketplace add JirakJ/proto-forge`), see ADR-0030.

```bash
# what a given runtime can actually afford
python3 scripts/skill-budget-lint.py                                     # measures the installed set (ADR-0024)
AGENTIC_OS_CONTEXT_TOKENS=1000000 python3 scripts/skill-budget-lint.py   # override the denominator (ADR-0023)
```

## Install

```bash
git clone https://github.com/JirakJ/agentic-os-agi.git
cd agentic-os-agi

# register the marketplace with Claude Code
claude plugin marketplace add .

# install the plugins you want
claude plugin install core-orchestration@agentic-os-agi
claude plugin install governance-gates@agentic-os-agi
claude plugin install memory-obsidian@agentic-os-agi
claude plugin install self-evolution@agentic-os-agi
claude plugin install long-horizon@agentic-os-agi
claude plugin install autonomic-loop@agentic-os-agi
claude plugin install core-guardrails@agentic-os-agi
claude plugin install memory-fabric@agentic-os-agi
```

`governance-gates` depends on `core-orchestration` (it calls `doctor.py`); `self-evolution` depends
on both (it evaluates the release tooling and mines the audit trail); `long-horizon` depends on all
three (missions feed the frontier, which reads the eval suite and the miner); `autonomic-loop`
depends on all four — it is pure policy over their tools. Claude Code resolves and installs
dependencies automatically.

Verify the install:

```bash
/os-doctor          # validate every component
/plugin list        # confirm the plugins you installed are active
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
/mission            # durable goals that outlive sessions — resumable, blockable, honest to close
/frontier           # the self-model and the evidence-ordered answer to "what should we learn next"
```

The ordering is deliberate and non-negotiable (ADR-0008): verification exists *before*
self-authoring, because a system that modifies itself without measuring the result is taking a
random walk. And the loop proposes rather than auto-merges (ADR-0010) — the one irreversible step,
modifying core logic, always has a gate. This is the governance layer paying off: ADRs justify
self-modifications, atomic commits make them individually revertible, and the audit trail is the
raw material the loop learns from.

## Long-horizon autonomy

`long-horizon` removes the hardest ceiling — the context window as the bound on how far a goal
can reach. **Missions** are durable, git-tracked goal state (ADR-0011): decomposed into
session-sized verifiable steps, injected as a brief at session start so a fresh session resumes
cold, refusing dishonest completion by construction. The **self-model** (ADR-0012) derives what
the system can actually do — from eval scores, the inventory, and the audit trail, never from
assertion — and reports *measured*, *unmeasured* and *used* as three distinct claims. The
**frontier** (ADR-0013) fuses the self-model, blocked missions and mined friction into an
evidence-ordered learning agenda: weakness > blocked intent > coverage gaps > friction. The
frontier orders; the loop's gates still decide. Vision enters as a mission, not a frontier edit.

## The autonomic layer

Everything above waits to be invoked; `autonomic-loop` removes the waiting (ADR-0014). Hooks are
the one deterministic trigger surface Claude Code offers, so the loop's policy lives there, in a
plugin that owns *when* things fire and none of *how*:

- **PostToolUse** — an edit under `plugins/` or `adr/` marks the session core-dirty.
- **Stop** — a core-dirty session runs the capability suite before it may finish. A regression
  blocks the stop with the failing capability named and the fix path; a green run clears the
  debt. A turn does not end with the fleet measurably worse and nobody told.
- **SessionEnd** — the trail is mined and the top proposals staged, after the human has left.
- **SessionStart** — the next session opens knowing the verified state, any standing
  regression, and the staged proposals — with the skills to apply named explicitly.

`AGENTIC_OS_AUTONOMIC=off` switches every reflex off without uninstalling anything: the system
degrades to manual, losing automation and nothing else. That separability is the point — and the
adoption gate is untouched: the loop senses, verifies, stages and blocks; it never authors or
adopts (ADR-0010). Inspect it any time with `/autonomic`.

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
