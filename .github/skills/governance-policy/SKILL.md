---
name: governance-policy
description: Explain and troubleshoot the agentic OS governance gates — what each hook blocks, why, and how to resolve a block correctly. Use this whenever a hook blocks or denies something, whenever the user asks "why was that blocked", "why can't I read this file", "what is commit-adr-gate", "how do I disable this hook", or when a session ends in a block and the right fix is unclear. Also use it when adding a new gate, tuning an existing one, or when someone proposes turning a gate off.
allowed-tools: Bash, Read, Grep
metadata:
  version: 1.0.0
  layer: L1-core
---

# Governance Policy

What the gates enforce, why each one exists, and how to get past one honestly.

## The gates

| Hook | Event | Effect | Enforces |
|---|---|---|---|
| `secret-guard` | PreToolUse | deny | credentials never enter the transcript |
| `core-change-tracker` | PostToolUse | records | which components a session touched |
| `manifest-validator` | PostToolUse | block | a component never stays broken past the edit that broke it |
| `commit-adr-gate` | Stop, SubagentStop | block | atomic commits + decision records (ADR-0005) |
| `audit-logger` | PostToolUse | records | append-only trail of every tool call |

## secret-guard denied a read

It matched a credential path (`.env`, `id_rsa`, `.aws/credentials`, `*.pem`) or spotted a live
credential shape in content about to be written.

**Correct resolutions**, in order:
1. You do not need the value. Reference the variable name and let the runtime resolve it.
2. You need to know a variable *exists*: `test -f .env && echo present` is not blocked.
3. You genuinely need one specific value: ask the user to paste that value only.

`.env.example` and friends are explicitly allowed — they are documentation.

**Not a resolution**: renaming the file to dodge the pattern. If you find yourself doing that, the
design is wrong, not the gate.

## manifest-validator blocked a write

`doctor.py` rejected the component you just wrote. The block carries the findings. Fix them now —
a broken manifest loads silently and does nothing, so the failure resurfaces later as "why does
this skill never trigger", which is a far more expensive question.

Common causes: `skill.json` version drifting from `metadata.version`; a component directory under
`.claude-plugin/`; an ADR reference with no record behind it; a hook script that lost `+x`.

## commit-adr-gate blocked the turn

Core logic is uncommitted, or a behavioural change has no decision record. The block lists each
component with the exact `git add` / `git commit` lines.

**Correct resolutions:**
- Commit each component separately, as printed. That is the whole contract — one component per
  commit is what makes `git revert` a working undo (ADR-0002).
- The change was exploratory: `git checkout -- <paths>`. Discarding is a legitimate outcome.
- An ADR is demanded and the decision is real: write it, commit it alone, reference it from the
  implementation.

**Not a resolution**: `git add -A && git commit -m "wip"`. That satisfies the gate and destroys the
thing the gate protects. The gate checks that the tree is clean; only you can check that the commits
are atomic.

### The ADR demand looks wrong

Sometimes it is. The marker set keys on contract-shaped diffs (`allowed-tools`, `description`,
`dependencies`, blocking rules) and it is deliberately tuned toward false positives — an
unnecessary ADR costs five minutes; a missing one costs a year of not knowing why.

If it fires wrongly more than about once a week, that is a real signal: the markers are too eager
and `commit_adr_gate.py` needs narrowing. Change the gate, with an ADR. Do not work around it.

## Reading the audit trail

```bash
ls "${CLAUDE_PLUGIN_DATA}/audit/"
python3 -c "
import json,sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get('components'):
        print(r['ts'], r['tool'], ','.join(r['components']))
" "${CLAUDE_PLUGIN_DATA}/audit/$(date +%F).jsonl"
```

One JSON object per line, one file per day. Records actions, never payloads — a trail containing
file contents is a second copy of your secrets, which is why `summarise()` truncates to a label.

## Turning a gate off

You can. `/plugin disable governance-gates`, or drop the matcher from `hooks.json`.

Before you do, note what that costs: the gates are what make ADR-0002's rollback story true rather
than aspirational. A month of ungated sessions produces a history where `git revert` no longer
restores one component, and you find that out on the day you need it. Nothing warns you in between.

If a gate is wrong, fix the gate — it is versioned core logic like everything else, and improving it
is a `feat(hook/...)` commit with an ADR. That path takes twenty minutes and leaves the guarantee
intact.

## Adding a gate

1. ADR first: what it blocks, what it costs, what false-positive rate would make it wrong
2. Script in `hooks/scripts/`, importing `_lib` for the protocol
3. Wire into `hooks/hooks.json` with a timeout
4. Test it with real payloads: `echo '{"tool_name":"Write",...}' | python3 hooks/scripts/your_gate.py`
5. `chmod +x` — `doctor.py --hooks` fails the build otherwise
6. `/reload-plugins`; hook changes are not hot-reloaded

Hooks run synchronously and stack, so a gate spends its budget on every tool call whether it fires
or not. Keep the hot path import-light (see ADR-0006). A gate that starts blocking something it
previously allowed is a **major** bump — it changes what the system permits.
