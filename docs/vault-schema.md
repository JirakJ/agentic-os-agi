# Vault schema (schema: 2)
Authoritative copy of plugins/memory-fabric/skills/obsidian/references/vault-layout.md.
Folders: 00-inbox (captures), 10-daily, 20-decisions, 30-retros (route: skill-forge |
guardrail-forge | adr | none), 40-entities, 50-projects (MOCs), 60-skills-kb,
70-telemetry (queue/*.jsonl schema_version 3 + telemetry.md rollup), 90-moc.
All notes: YAML frontmatter with `schema: 2` + type-specific keys from _templates/.
Merge policy: daily/decisions/retros/telemetry use git merge=union. Telemetry JSONL
record: {schema_version, ts, session_id, host, event, detail} - one line, < 4 KiB.
