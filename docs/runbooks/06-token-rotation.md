# Runbook: credential rotation (Obsidian REST key, Marketplace publish token, MCP secrets)
1. Obsidian: regenerate the key in the Local REST API plugin settings; update the
   OBSIDIAN_REST_API_KEY export (shell profile / OS keychain). Nothing in-repo changes -
   configs reference ${OBSIDIAN_REST_API_KEY}.
2. JetBrains PUBLISH_TOKEN: rotate on JetBrains Hub; update the env/keychain entry.
3. Copilot coding agent MCP secrets: rotate in repo Settings > Environments > copilot
   (COPILOT_MCP_* prefix).
4. Never write tokens into files - security-gate denies agent access to secret paths, and
   gitleaks in preflight + jj-sync is the second net. If a token DID leak: rotate first,
   then purge history (git filter-repo) on the affected repo.
