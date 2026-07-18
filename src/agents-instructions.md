# Agentic OS - Agent Instructions

Applies to every coding agent working in this repository (Claude Code, GitHub Copilot
coding agent/CLI/IDE agent mode, and any AGENTS.md-aware tool).

## Non-negotiables
- Production-ready only: no placeholders, TODOs, stubs, mocks, lorem ipsum, or half-written
  branches in committed code.
- Conventional Commits, SemVer, lockstep releases: code, docs, CHANGELOG, plugin manifests
  and marketplace listing move together in one atomic commit.
- Real error handling, strong typing, SOLID/DDD boundaries. All code, comments, commits and
  docs in English.

## Definition of done
- `scripts/preflight.sh` exits green: gitleaks -> lint/type errors -> build -> full tests ->
  SAST (Opengrep, ERROR severity, baseline ratchet) -> dependency vulns (osv-scanner,
  CVSS >= 7 blocks) -> runnability smoke.
- The commit-integrity gate verifies a fresh green attestation for the exact staged tree
  before any `git commit`/`git push`. If blocked: run `scripts/preflight.sh`, fix what is
  red, retry. Never attempt to bypass, weaken, or edit the gates - gate files are protected
  and require explicit human approval (/gate-unlock) plus an ADR.

## Memory
- Long-term memory lives in the Obsidian vault (two-tier memory: this git repo = executable
  assets; vault = knowledge). Read it via the memory-fabric MCP server; write session
  learnings via the memory-capture skill. Durable decisions go to 20-decisions/ + adr/.
