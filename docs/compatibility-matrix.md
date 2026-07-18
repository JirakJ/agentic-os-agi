# Dual-runtime compatibility matrix (v3.0.0)

Legend: native = first-class | generated = produced by build-adapters.py | parity = via
git hooks + CI + rulesets | manual = one-time setup | n/a = deliberately not ported.

| Capability | Claude Code | Copilot VS Code | Copilot CLI | Copilot coding agent | Copilot JetBrains |
|---|---|---|---|---|---|
| Skills (SKILL.md) | native (plugins) | native `.github/skills` + `.claude/skills` (auto) | native (`.github/skills`, `~/.copilot/skills`) | native (repo skills) | preview (enable agent mode) |
| Rules / instructions | `.claude/rules` (generated) | `copilot-instructions.md` + `instructions/*.instructions.md` (generated) + AGENTS.md (`chat.useAgentsMdFile`) | AGENTS.md + instructions | copilot-instructions + applyTo instructions + AGENTS.md | AGENTS.md + instructions |
| Commands / prompts | plugin `commands/` (generated) | `.github/prompts/*.prompt.md` (generated, preview) | skills act as slash commands | not read (skills cover it) | prompt files (preview) |
| Agents | plugin `agents/` (generated) | `.github/agents/*.agent.md` (generated; model = string) | same (model MUST be string) | same (ignores handoffs) | same (GA) |
| MCP | `.mcp.json` (generated) | `.vscode/mcp.json` `servers` (generated; 128-tool cap/request) | `.github/mcp.json` + `~/.copilot/mcp-config.json` | repo Settings > Copilot (paste `.github/mcp.json` mcpServers; `COPILOT_MCP_*` secrets) - manual | IDE MCP settings / `.github/mcp.json` |
| Deterministic commit gate | PreToolUse deny (native) | parity (lefthook + CI + ruleset) | parity | parity - ruleset is the ONLY layer it cannot evade | parity (agent hooks preview, not relied on) |
| Session memory capture | SessionEnd hooks (native) | memory-capture skill (explicit) | memory-capture skill | CI-side possible; PR description discipline | memory-capture skill |
| Telemetry | hooks (native) | skill-emitted + rollup | skill-emitted | CI preflight records | skill-emitted |
| PreCompact anchor / subagent bridge | native | n/a (runtime manages context) | n/a | n/a | n/a |

Policy prerequisites (Copilot Business/Enterprise): MCP servers in Copilot (off by
default), Copilot CLI, coding agent enablement, Editor preview features (JetBrains
skills/prompt files), Agent Skills. Coding-agent MCP + setup steps are per-repo - automate
across the org with `gh api` or the template-repo pattern (see copilot-rollout-ops skill).
