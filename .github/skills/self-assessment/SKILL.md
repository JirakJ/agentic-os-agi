---
name: self-assessment
description: Ground any claim about what this system can do in the evidence-derived self-model, and read the learning frontier to decide what to improve next. Use this whenever the user asks "what are you good at", "what are this system's capabilities", "where are we weak", "what should we learn or build next", "how is our coverage", before planning work that assumes a capability exists, or when prioritising between improvement candidates. Also use it to interpret self-model and frontier output rather than taking the raw numbers at face value.
allowed-tools: Bash, Read
metadata:
  version: 1.0.0
  layer: L1-core
---

# Self-Assessment

Claims about capability are cheap; calibrated ones are derived. The self-model computes what this
system can do from evidence — eval scores, the component inventory, the audit trail — and is never
edited by hand (ADR-0012). The frontier orders what to learn next from that same evidence
(ADR-0013). This skill is how to read both without fooling yourself.

## Deriving the model

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/selfmodel.py"            # live: runs the eval suite (truth)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/selfmodel.py" --cached   # last snapshot (faster, staler)
```

The model reports three distinct things. Keep them distinct:

- **Measured** — capabilities with eval scores and a trend against baseline. This is the only place
  the word "good at" is allowed to come from.
- **Unmeasured** — plugins no eval exercises. This is not "assumed fine"; it is *ignorance*, and it
  is where regressions hide (ADR-0008). Say "unmeasured", never "fine".
- **Used** — audit-trail frequency. Engagement, not quality: a component called often is relied on,
  which raises the stakes of it being unmeasured, but says nothing about it being good.

## Reading it honestly

- **Believe the model over intuition.** If it says a capability is weak, it is weak — the number
  came from a verifier, the intuition came from vibes. The legitimate challenge is "the eval
  measures the wrong thing", and the response to that is a better eval, never a mental override.
- **Thin evidence is a caveat, not a footnote.** A capability resting on one eval is one angle of
  measurement; treat its score as provisional and say so when reporting it.
- **The model understates by construction.** Model-dependent qualities — judgement, prose, whether
  a skill improves reasoning — have no deterministic eval yet, so they do not appear. Absence from
  the model means *unmeasured*, not *absent*. State that bias when summarising capabilities.

## The frontier: what to learn next

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/frontier.py"
```

The order is fixed by evidence severity and worth internalising: **weakness** (measured harm)
before **blocked intent** (stalled committed work) before **coverage gaps** (places regressions
hide) before **friction** (repeated cost). When the top item feels wrong, check its evidence — the
item carries it precisely so the ranking can be interrogated. Overriding the order is legitimate;
doing it silently is not.

An empty frontier is the goal state, not a malfunction. And the frontier cannot originate vision —
it only orders responses to evidence. New ambition enters as a mission (ADR-0011), which then
surfaces here if it blocks.

## From assessment to action

A frontier item is not authorised work; it still walks the loop's gates: shape it with
`capability-proposal`, implement via `skill-author`, verify with the eval suite, adopt through an
ADR and an atomic commit (ADR-0008, ADR-0010). Assessment tells you *what first and why* — the
gates still decide *whether*.
