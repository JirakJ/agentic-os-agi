---
name: meeting-notes-to-actions
description: Convert raw meeting notes or transcripts into decisions, owned action items with due dates, and vault records - plus a follow-up message draft. Use whenever the user pastes meeting notes, mentions a meeting recap, action items, minutes, "zapis ze schuzky", or asks what was agreed.
license: MIT
metadata:
  version: "3.0.0"
---

# Meeting Notes to Actions

## Procedure
1. Parse the input into: decisions (what was agreed + by whom), actions (verb + owner +
   due date; flag any action missing an owner or date and propose one), open questions,
   and information items. Discard chit-chat.
2. Confirm ambiguous owners/dates with the user in ONE compact question set, not
   piecemeal.
3. Write to the vault: decisions -> `20-decisions/` notes (status: accepted, project
   linked); the meeting itself -> `10-daily/` log entry with wiki-links to entities;
   new people/teams -> `40-entities/`.
4. Output for the user:
   - Action table: owner | action | due | source line.
   - Follow-up message draft (email/Teams) summarizing decisions + actions, addressed to
     participants, neutral-professional tone, ready to send.
5. If any action belongs to the user, offer to add it to next week's weekly-status
   "Next week" section.

## Validation
- Every action has owner + due date (or an explicit flag); every decision is in the vault;
  the follow-up draft contains nothing that was not in the notes.
