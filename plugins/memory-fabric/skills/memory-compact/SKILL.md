---
name: memory-compact
description: Periodic vault maintenance - refine inbox captures into proper notes, merge duplicates, archive stale items, keep MOCs current. Use when the user says clean up the vault, process inbox, vault maintenance, weekly review, or when 00-inbox has more than 10 unprocessed captures.
license: MIT
metadata:
  version: "3.0.0"
---

# Memory Compact

Keeps the vault high-signal so SessionStart injection stays cheap and relevant.

## Procedure
1. Process `00-inbox/`: for each `capture-*.md`, extract durable content into daily notes /
   decisions / retros / entities (per memory-capture rules), then DELETE the capture.
   Nothing lives in the inbox for more than a week.
2. Deduplicate `40-entities/`: merge aliases into one note, keep `aliases:` frontmatter.
3. `20-decisions/`: mark superseded decisions (`status: superseded`, link successor).
4. Update `50-projects/` MOCs: current status line, links to fresh decisions/retros.
5. Telemetry: run `python3 scripts/rollup-telemetry.py`; check `processed/` retention
   (drainer auto-prunes at 30 days) and report queue size.
6. Finish with `bash scripts/jj-sync.sh` and a one-paragraph maintenance summary in
   today's daily note.
