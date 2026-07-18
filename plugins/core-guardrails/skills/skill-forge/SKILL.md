---
name: skill-forge
description: Create, evaluate, prune, and promote skills for this Agentic OS so it keeps improving itself. Use whenever the user wants to turn a repeated workflow into a skill, improve or benchmark an existing skill, fix a skill that is not triggering, or run the periodic skill review. Also use when a retro note in the vault suggests a recurring workflow worth automating.
license: MIT
metadata:
  version: "3.0.0"
---

# Skill Forge

Meta-skill: the OS's self-evolution loop for skills. Skills are runtime-neutral
(SKILL.md loads in Claude Code AND GitHub Copilot), so one well-made skill upgrades every
surface at once.

## Where skills live
- Source of truth: `plugins/<plugin>/skills/<name>/SKILL.md` (business-ops, day-job,
  memory-fabric, core-guardrails).
- `scripts/build-adapters.py` copies them to `.github/skills/` for Copilot repos.
- Experiments: start in `~/.claude/skills/<name>/` (personal scope), promote into a plugin
  once proven.

## Authoring rules (Agent Skills spec + budget)
1. Frontmatter: `name` == directory name, <= 64 chars, lowercase-hyphen; `description`
   <= 1024 chars and "pushy" (state WHAT it does + WHEN to trigger, including synonyms the
   user actually says); optional `license`, `metadata.version`. `allowed-tools` is
   pre-approval, NOT a sandbox - never rely on it for safety.
2. Body < 500 lines; move detail into `references/` (read on demand) and deterministic
   work into `scripts/` (execute, don't load). One level of file references only.
3. Numbered, reproducible steps with explicit validation gates ("run X, expect Y").
4. After any skill change run `python3 scripts/skill-budget-lint.py` (listing budget) and
   `python3 scripts/validate-copilot.py` (cross-runtime validity). Both must pass.

## Creating a skill from a session (reproducible procedure)
1. Extract from the conversation: trigger phrases, tool sequence, corrections the user
   made, output format. Confirm the happy path with the user in <= 5 bullets.
2. Draft `SKILL.md` per the rules above; put reusable prompts/templates in `assets/`.
3. Test: run 3 realistic prompts THROUGH the skill (read SKILL.md, follow it exactly).
   Each must produce the expected artifact without improvisation. Fix the skill, not the run.
4. Register: place in the owning plugin, run `python3 scripts/build-adapters.py`, then
   `bash scripts/validate-all.sh`.
5. Version lockstep: skill changes ship with a distribution release (`scripts/release.sh`).

## Pruning and promotion review (monthly)
1. Read skill usage counts from the telemetry rollup (`70-telemetry/telemetry.md`).
2. Unused 60+ days AND not seasonal -> move to `~/.claude/skills/_archive/` (out of the
   listing budget). Heavily used personal experiment -> promote into a plugin.
3. Re-run `skill-budget-lint.py`; keep total under 90% of the listing budget.
