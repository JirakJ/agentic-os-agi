---
name: weekly-status
description: Produce the ISO-week (W##) enterprise status report - accomplishments, in-progress, risks, next week, asks - from vault daily notes, commits, and meeting notes. Use whenever the user mentions weekly status, W report, status update, "tydenni report", Friday report, or a manager asking what was done this week.
license: MIT
metadata:
  version: "3.0.0"
---

# Weekly Status (W##)

Audience: engineering management. Facts with links, zero filler, outcomes over activity.

## Procedure
1. Determine the ISO week `W##` and date range (Mon-Fri, Europe/Prague).
2. Gather inputs: vault `10-daily/` notes in range, `git log --since --author` across the
   week's repos if available, meeting-notes-to-actions outputs, open decision notes.
3. Compose exactly these sections:
   - **Done** (max 6 bullets): outcome + measurable effect + link (PR/ticket/doc).
   - **In progress** (max 4): state + ETA + current blocker if any.
   - **Risks / blockers**: each with impact, owner, and the ask that unblocks it.
   - **Next week** (max 5): committed outcomes, not intentions.
   - **Asks**: decisions or resources needed, each addressed to a named role.
4. One screen max. Rewrite any activity-phrased bullet ("worked on X") into an outcome.
5. Deliver as markdown ready to paste (email/Teams), and append a copy to
   `10-daily/` week-closing note in the vault.

## Validation
- Every Done bullet has a link; every risk has an owner + ask; fits on one screen.
