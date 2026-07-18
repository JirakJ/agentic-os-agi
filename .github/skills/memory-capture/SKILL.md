---
name: memory-capture
description: Distill the current session into durable vault memory - decisions, blockers, root causes, next steps. Use when the user says remember this, capture this, save to memory, log this decision, "uloz do pameti", at the end of significant work sessions, and on Copilot surfaces where automatic SessionEnd capture does not exist. This is the explicit write-path of the two-tier memory.
license: MIT
metadata:
  version: "3.0.0"
---

# Memory Capture

Claude Code captures automatically via SessionEnd hooks; this skill is the *explicit* and
*cross-runtime* path (GitHub Copilot has no session hooks - invoke this instead).

## Procedure
1. Distill the session into <= 10 bullets across: decisions (with WHY), blockers + root
   causes, things learned, next steps. No transcripts, no code dumps - links to commits.
2. Append to today's daily note `10-daily/YYYY-MM-DD.md` under `## Log` (create the file
   from `_templates/daily.md` if missing).
3. Durable decision made? Create `20-decisions/YYYY-MM-DD-slug.md` from
   `_templates/decision.md` (status: accepted). If it changes the Agentic OS itself, also
   propose a MADR ADR in `docs/adr/`.
4. Gate/skill friction occurred? Add `30-retros/YYYY-MM-DD-slug.md` from
   `_templates/retro.md` - retros are the input queue for skill-forge and guardrail-forge.
5. New person/client/system encountered? Upsert `40-entities/<name>.md` and wiki-link it.
6. Write via the obsidian skill (REST first, file fallback). Confirm to the user what was
   written where, in one line per note.

## Validation
- Every written note passes: frontmatter present, `schema: 2`, correct folder, filename
  pattern, and at least one wiki-link where an entity was mentioned.
