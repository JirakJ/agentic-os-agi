# memory-obsidian

Three-layer memory (ADR-0003): an Obsidian vault as the human knowledge base (L3), a local SQLite
FTS5 + sqlite-vec hybrid retrieval index over it (L4), and durable session memory kept fresh at
session end. It answers one question — "what did the user, or a past session, already write,
decide or capture?" — and answers it in snippets, not whole notes, so recall costs tens of tokens
instead of thousands.

## Components

| Component | Kind | Purpose |
|---|---|---|
| `commands/recall.md` (`/recall`) | command | Search the vault and episodic memory for what was already written or decided |
| `commands/vault-index.md` (`/vault-index`) | command | Rebuild or refresh the local retrieval index |
| `skills/vault-recall` | skill | Retrieve what the user already knows before answering from general knowledge; forked context |
| `skills/vault-capture` | skill | Write a note into the vault or episodic memory when something durable is worth keeping and lives nowhere else |
| `scripts/recall.py` | script | Query engine behind `/recall` |
| `scripts/index_vault.py` | script | Incremental indexer behind `/vault-index` — re-reads a file only when its mtime *and* hash both moved |
| `scripts/vaultdb.py` | script | The hybrid retrieval engine: BM25 + vector search fused with RRF |
| `scripts/capture.py` | script | Vault/episodic-memory write path behind `vault-capture` |
| `hooks/scripts/session_memory.py` | hook (`SessionEnd`) | Keeps the L4 index fresh for whatever the session wrote — incremental, non-blocking |
| `.mcp.json` | config | Obsidian Local REST API MCP server (`OBSIDIAN_API_KEY`), used by the vault-capture/recall path for direct vault reads/writes |
| `userConfig.vaultPath` | manifest field | Absolute path to the vault (default `~/Documents/Vault`) |
| `userConfig.captureFolder` | manifest field | Vault-relative folder for session captures (default `10-Inbox/agent-capture`) |

No agents, no evals of its own — `self-evolution`'s `recall-precision` eval is what measures this
plugin's retrieval quality (hybrid recall ranks the note that answers the query first, and returns
nothing for a genuine no-match) rather than an eval shipped here.

## The three layers

- **L3 — the Obsidian vault.** The human knowledge base. This plugin **reads** it (`recall.py`,
  `vaultdb.py`) and can **write** to it deliberately, via the `vault-capture` skill, when Claude
  judges something durable is worth keeping — never automatically. `session_memory.py` explicitly
  does *not* write session summaries to the vault: "what is worth keeping is a judgement call, and
  a hook cannot make it."
- **L4 — the hybrid retrieval index.** A local SQLite FTS5 + sqlite-vec index over both the vault
  and episodic memory. Fully derived data (ADR-0003): `--rebuild` is always safe and loses nothing.
  Without a local embedding model (`sqlite-vec` + `model2vec`), the vector arm is off and recall
  runs on BM25 alone — functional, just without semantic matching; the output says so explicitly
  (`[BM25 only]`).
- **Session memory.** `session_memory.py` refreshes L4 at `SessionEnd` so the *next* session can
  recall what *this* one committed — reindexing only, never a write to the vault itself.

## How this relates to `memory-fabric`

ADR-0021 resolves what looks like a contradiction between two independently-grown memory designs
into a split by axis, not by plugin:

| | Owner |
|---|---|
| L3 vault — **write** (automatic, crash-safe queue) | `memory-fabric` |
| L3 vault — **read** (recall, retrieval) | this plugin |
| L3 vault — **write** (deliberate, skill-invoked) | this plugin (`vault-capture`) — a judgement call, not automatic |
| L4 SQLite retrieval index | this plugin, additive — `memory-fabric` has no equivalent |

Both plugins can legitimately write to the vault: `memory-fabric`'s hook enqueues capture
candidates from the transcript automatically; this plugin's `vault-capture` skill writes when
Claude deliberately decides something is worth keeping. Neither replaces the other, and installing
one does not make the other redundant — see ADR-0021 before changing either plugin's capture path.

## Usage

```bash
export AGENTIC_OS_VAULT="$HOME/Documents/Vault"
export OBSIDIAN_API_KEY="…"   # from the Obsidian Local REST API plugin

/vault-index --rebuild
/recall "what did I decide about X"
```

Report what came back — the answer, and the paths it came from. Read a full note with `Read` only
if a snippet shows the detail is there and it matters. If a note contradicts what you were about to
say, the note wins on facts about the user's own systems and decisions — surface the conflict
rather than quietly overwriting it. `[BM25 only]` in the footer means rephrase using the vault's own
vocabulary before concluding nothing is there; it does not mean recall is broken.
