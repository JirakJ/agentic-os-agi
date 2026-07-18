---
name: content-pipeline
description: Turn engineering work and ideas into published content for thinkdifferent.blog and LinkedIn - from topic capture through draft, edit pass, and cross-post adaptation. Use whenever the user mentions blog post, article, LinkedIn post, content calendar, "napis clanek", publishing, or wants to repurpose a session/retro into content.
license: MIT
metadata:
  version: "3.0.0"
---

# Content Pipeline

Voice: direct, dense, technical, first-person practitioner; concrete numbers and code over
generalities; no hype adjectives; English for the blog, English for LinkedIn.

## Procedure
1. **Source**: pull the raw material - a vault retro/decision, a shipped feature, or the
   user's prompt. Extract the one non-obvious claim the piece proves.
2. **Blog draft (thinkdifferent.blog)**: 900-1500 words; structure: hook (problem cost) ->
   context -> the approach with real code/config -> measured result -> what breaks /
   trade-offs -> takeaway. Every claim gets evidence (benchmark, diff, screenshot note).
3. **Edit pass**: cut 20% by length; verify every command/code block actually runs
   (execute it); one idea per paragraph; title states the outcome, not the topic.
4. **LinkedIn adaptation**: 120-220 words; first line is the hook (no "I'm excited");
   3-5 short paragraphs or a tight list; one question at the end; link to the blog post;
   3 hashtags max.
5. **Log**: append the published URLs and topic to `50-projects/content.md` in the vault
   (create from project-moc template if missing) so the pipeline tracks cadence.

## Validation
- All code in the piece executed successfully during the edit pass.
- Blog and LinkedIn versions make the SAME claim with different depth - no drift.
