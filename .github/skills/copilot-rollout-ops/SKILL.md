---
name: copilot-rollout-ops
description: Operate the GitHub Copilot enterprise rollout across engineering teams - enablement sessions, adoption metrics, policy configuration, champion communications, and per-repo standards (instructions, skills, MCP, rulesets). Use whenever the user mentions Copilot rollout, adoption, enablement, Copilot policies, seats, training engineers on Copilot, or distributing AI standards across the org.
license: MIT
metadata:
  version: "3.0.0"
---

# Copilot Rollout Ops

The dual-runtime design makes this OS the distribution vehicle: the same `.github/`
artifacts every engineer's repo gets (instructions, skills, prompts, agents, MCP, CI gate).

## Org configuration checklist (admin asks, verify each)
1. Policies (Org Settings > Copilot): enable **MCP servers in Copilot** (off by default),
   **Copilot CLI**, **coding agent** for selected orgs, **Editor preview features** (needed
   for JetBrains skills/hooks previews), **Agent Skills**.
2. Org custom instructions set (GA); org `.github` repo hosts shared custom agents.
3. Repo standard via template repo: `.github/copilot-instructions.md`, `instructions/`,
   `skills/`, `prompts/`, `mcp.json`, `copilot-setup-steps.yml`, `lefthook.yml`,
   CI caller of `jj-preflight.yml`, plus a ruleset requiring the `preflight` check -
   the server-side gate even the coding agent cannot bypass.
4. Coding agent MCP is per-repo (Settings > Copilot > Coding agent) - script it with
   `gh api` across repos; secrets prefixed `COPILOT_MCP_` in the `copilot` environment.

## Enablement session (repeatable 60-min format)
1. 10 min: what changed this month (features relevant to THEIR stack only).
2. 30 min: live task from their actual backlog using instructions + one skill.
3. 10 min: the guardrail story - why the preflight gate exists, how to read a block.
4. 10 min: capture friction -> vault `30-retros/` with route, feeding next session.

## Adoption metrics (monthly)
1. Pull org Copilot metrics (seat activity, suggestions accepted, chat usage) via the
   Copilot metrics API; join with repo standard coverage (% repos on the template).
2. Report: adoption %, top friction themes from retros, next month's two interventions.
3. Log the report in the vault (`50-projects/copilot-rollout.md`).
