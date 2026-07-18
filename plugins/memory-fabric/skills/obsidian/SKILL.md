---
name: obsidian
description: Read and write the user's Obsidian vault (two-tier memory) - daily notes, decisions, retros, entities, project MOCs. Use whenever the user says vault, Obsidian, note, daily note, decision log, retro, "zapis do vaultu", "remember this", or when any skill needs durable memory. Prefer the Local REST API; fall back to direct file access in the vault checkout.
license: MIT
metadata:
  version: "3.0.0"
---

# Obsidian Vault Access

Vault root: `$JJ_VAULT_ROOT` (default `~/jj-vault`). Structure and note schemas:
`references/vault-layout.md`. All notes carry YAML frontmatter with `schema: 2`.

## Access strategy (circuit breaker)
1. **REST API first** (Obsidian running): base `http://127.0.0.1:27123`, header
   `Authorization: Bearer $OBSIDIAN_REST_API_KEY`.
   - Read: `GET /vault/{path}` ; Write: `PUT /vault/{path}` (body = full markdown);
     Append: `POST /vault/{path}` ; Search: `POST /search/simple/?query=...`.
   - Or use the `obsidian-vault` MCP server (same plugin serves `/mcp/`), configured in
     `.mcp.json` / `.vscode/mcp.json` / `.github/mcp.json`.
2. **File fallback** (API down / headless): read-write files directly under the vault
   checkout. Same markdown, same schemas. Never edit `.obsidian/`.
3. After a failed API call, use files for the rest of the session (do not retry per call).

## Write rules
1. New notes ALWAYS start from `_templates/` (daily, decision, retro, entity,
   project-moc, capture). Keep the frontmatter keys - Bases dashboards query them.
2. Filenames: `10-daily/YYYY-MM-DD.md`, `20-decisions/YYYY-MM-DD-slug.md`,
   `30-retros/YYYY-MM-DD-slug.md`, `40-entities/<entity>.md`, `50-projects/<project>.md`.
3. Wiki-link entities (`[[client-x]]`) so graph and MOC views stay useful.
4. Confidential boundary: Employer/client-confidential material goes into its dedicated vault,
   never this one (security-gate denies cross-boundary writes).
5. Vault sync is `scripts/jj-sync.sh` on a 15-min scheduler; do not git-push the vault
   manually mid-session unless asked.
