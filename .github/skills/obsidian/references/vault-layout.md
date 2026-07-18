# Vault layout and note schemas (schema: 2)

| Folder | Purpose | Template |
|---|---|---|
| 00-inbox | Raw captures awaiting refinement | capture.md |
| 10-daily | One note per day: log, decisions inline, next steps | daily.md |
| 20-decisions | Durable decisions (lightweight ADR twin) | decision.md |
| 30-retros | Friction/root-cause notes feeding the forges | retro.md |
| 40-entities | People, clients, tools, systems | entity.md |
| 50-projects | Project MOCs linking everything | project-moc.md |
| 60-skills-kb | Longform knowledge behind skills | (freeform) |
| 70-telemetry | JSONL queue + weekly telemetry.md rollup | telemetry-rollup.md |
| 90-moc | Top-level maps of content | (freeform) |

Frontmatter keys queried by dashboards: `schema`, `type`, `status`
(proposed|accepted|superseded for decisions), `project`, `tags`, `captured`/`date`.
Merge policy: `10-daily`, `20-decisions`, `30-retros`, `70-telemetry` use git
`merge=union` (append-only patterns), configured in the vault's .gitattributes.
