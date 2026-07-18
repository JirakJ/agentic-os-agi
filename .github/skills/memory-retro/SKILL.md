---
name: memory-retro
description: Run a structured retrospective on friction - a failed approach, a gate misfire, a slow workflow, a repeated mistake - and turn it into a vault retro note plus a concrete improvement action (skill change, gate tuning, or ADR). Use when the user says retro, post-mortem, "why did this keep failing", or when the same problem appears twice.
license: MIT
metadata:
  version: "3.0.0"
---

# Memory Retro

Retros are how the OS learns. Output = one `30-retros/` note + one routed action.

## Procedure
1. Facts first: what happened, expected vs actual, evidence (commands, telemetry records,
   commit SHAs). No blame, no adjectives.
2. Root cause: ask "why" until you reach a system cause (missing gate, wrong skill step,
   absent knowledge, tooling gap) - max 5 levels, stop at the first actionable one.
3. Write `30-retros/YYYY-MM-DD-slug.md` from `_templates/retro.md` with frontmatter
   `route:` set to one of: `skill-forge`, `guardrail-forge`, `adr`, `none`.
4. Route the action immediately:
   - skill-forge -> update/create the skill now (follow skill-forge procedure).
   - guardrail-forge -> tune allowlist/gate now (follow guardrail-forge procedure).
   - adr -> draft the MADR ADR in docs/adr/ and link it.
5. Link the retro from today's daily note. One retro = one routed action, verified done.
