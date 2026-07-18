---
name: vault-capture
description: Write a note into the user's Obsidian vault or the agent's episodic memory — a decision made, a fact learned, a session summary worth keeping. Use this whenever the user says "save this", "note this", "capture this", "add this to my vault", "remember this", "write this down", or when a session produces a durable conclusion, a benchmark result, or a decision that future sessions would need and that lives nowhere else. Also use it at the end of substantial work when something non-obvious was learned that is not already captured in a commit or an ADR.
allowed-tools: Bash, Read
metadata:
  version: 1.0.0
  layer: L3-knowledge
---

# Vault Capture

Write it down when it will be needed and lives nowhere else. That second clause is the whole skill.

## Where a thing belongs

| The thing | Where | Why |
|---|---|---|
| Why a component behaves this way | **ADR** in `adr/` | It governs code; it belongs next to it, versioned with it |
| What a commit changed | **the commit message** | Already durable, already attributable |
| A durable fact learned about the user's systems | **vault (L3)** | Their knowledge base, their linking, their curation |
| What a session concluded, for future sessions | **memory/ (L2)** | Committed, versioned, machine-oriented |
| Session scratch, intermediate state | **nowhere** | It is noise; let it die with the session |

The most common mistake is capturing something already captured. A decision belongs in an ADR, not
in a vault note *about* the ADR. Before capturing, ask where else this already lives — if the
answer is "a commit" or "an ADR", stop.

## Capture

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capture.py" \
  --title "Hook latency on M-series" \
  --body "Python cold start ~40ms per hook; two PostToolUse hooks stack to ~85ms. Budget is 200ms, so there is room for one more gate before it needs measuring again." \
  --tags "agent,perf" \
  --folder "10-Inbox/agent-capture"
```

Or pipe the body:

```bash
echo "$SUMMARY" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capture.py" --title "Session: index rebuild"
```

Files land as `<folder>/YYYY-MM-DD-<slug>.md` with frontmatter recording title, timestamp, source
and tags.

## Transports

`capture.py` tries the Obsidian Local REST API first (`127.0.0.1:27124`, `$OBSIDIAN_API_KEY`), then
falls back to a direct filesystem write. REST is preferred because Obsidian stays authoritative over
its own index — a note written through it is immediately linkable and searchable, while a
filesystem write is invisible until Obsidian rescans.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capture.py" --check   # which transport is live
```

Both unavailable means capture fails loudly. That is correct — a silent capture failure is worse
than none, because the user believes the note exists.

## Writing the note

Write for the person who will find this in a year having forgotten everything:

- **Title**: what it is about, not what happened. "Hook latency on M-series", not "Session notes".
- **Body**: the conclusion first, then the evidence. Lead with what you would want to know at a
  glance.
- **Numbers**: keep them. "~40ms cold start" survives; "it was slow" does not.
- **Provenance**: name what produced the number — a benchmark, a measurement, an observation.
- **Tags**: match the user's existing taxonomy. Grep the vault before inventing a new tag; a
  one-note tag is a dead tag.
- **Links**: `[[Note Name]]` where a connection exists. An unlinked note in a linked vault is a
  note nobody finds again.

## Do not capture

- Anything that a commit or an ADR already says
- Session play-by-play — nobody rereads a transcript
- Anything you cannot state a future use for
- Secrets, tokens, credentials, in any form and under any framing

The vault is a curated knowledge base, not a log. Every note that does not earn its place makes
every other note harder to find — that cost is real and it compounds.

## After capture

The index picks up new notes at session end. To recall immediately in the same session:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/index_vault.py" --quiet
```
