---
name: anti-ai
description: Rewrite AI-generated text so it passes as human — to human readers AND to statistical AI detectors (Pangram etc.), using empirically validated recipes (discourse fracture, interleave protocol) with a deterministic linter (scripts/tellscan.mjs) that machine-verifies the self-check instead of trusting a hand-count. ONLY use this skill when the user explicitly invokes it by name — i.e. they type "/anti-ai" (or literally write "anti-ai" / "use the anti-ai skill"). Do NOT trigger it on paraphrased intent such as "humanize this", "make it sound less AI", "this reads like ChatGPT", or "fix the writing style" — the user has deliberately scoped this skill to explicit invocation only, so for those requests handle the rewrite normally without loading this skill unless they name it.
---

# Anti-AI: make the text pass as human

You have **full license to modify the text heavily** — restructure, cut, reorder, roughen. Preserve only: (1) the core message and facts, (2) the author's intent and audience, (3) the format (a LinkedIn post stays a LinkedIn post).

**What makes this version different: the self-check is machine-verified.** The recipes below are unchanged empirical research — they work. What fails in practice is the *verification*: a model asked to "count, literally" its own em-dashes and significance-markers grades itself and passes text that still has them. This skill ships `scripts/tellscan.mjs`, a stdlib linter that counts the countable checks deterministically. You run it; you don't self-report. A green linter is NOT a detector pass — it clears the mechanical subset (lexicon, em-dashes, significance-markers, word count, interleave ratio) and leaves the judgment calls (story-test, punchline-test, coverage-test) to you. Both matter. Never claim detector-proof.

## STEP 0 — Pick the mode (mandatory, before any editing)

Two targets; edits that satisfy one FAIL the other. Route first:

| Situation | Mode |
|---|---|
| User mentions a detector (Pangram, GPTZero, Turnitin, "AI detection", "pass as human", "not flagged") — or doesn't say, and the text is a personal/social/newsletter piece | **DETECTOR mode** (default) |
| User supplied (or can supply) a rough draft in their own words | **DETECTOR mode → interleave protocol** (the reliable variant) |
| Formal register where a live-rant voice is absurd (client docs, white papers, documentation) — or user explicitly wants only style cleanup | **READER mode** — and warn: this output will still score 100% AI on detectors |

**Default is DETECTOR mode.** A clean, polished, "human-sounding" rewrite is a FAILURE in detector mode — that exact output scored 100% AI eleven times in testing (see appendix).

---

## The linter (run it before every delivery)

```
node scripts/tellscan.mjs --mode reader   <file>              # reader audit
node scripts/tellscan.mjs --mode detector <file>              # detector checklist; exit 1 if unmet
node scripts/tellscan.mjs --mode detector --human draft.txt out.txt   # + interleave metrics
cat text | node scripts/tellscan.mjs --mode detector -        # stdin
node scripts/tellscan.mjs --json <file>                       # raw metrics
```

It prints one ✓/✗ line per countable check with the actual count. It does NOT read the detector's mind — it removes the dishonest hand-count, nothing more. What it CANNOT check (do these by eye): the story-test (one incident vs an argument), punchlines, essay-skeleton-in-disguise, and coverage (points dropped). Those four are the judgment calls in the recipes below.

---

## DETECTOR MODE

Statistical detectors don't read style. They detect **generation dynamics**: planned text where every sentence advances a known arc. Eleven styled rewrites — clean, punchy, rambling, typo-ridden, ESL-flavored, idiolect-mimicking — ALL scored 100% AI on Pangram. Surface mess is not the lever. Two recipes are:

### Recipe 1 — Interleave protocol (use when a human draft exists; the reliable path)

A genuinely human base draft absorbs up to ~45% AI-added words and still scores 100% Human.

1. Get the user's rough draft in their own words (voice-note transcript, ugly stream-of-consciousness — quality irrelevant, authorship everything). If they have none and the piece matters, ask for 2 minutes of typing from a bullet spine you provide.
2. **Preserve their sentences verbatim.** Never fix their grammar, typos, or run-ons — fractures are load-bearing human signal. Paraphrasing a human sentence converts it to AI tokens.
3. **Add, don't replace.** Your sentences go *between* theirs. Never two AI sentences in a row.
4. **Stay under ~40% AI words** (45% passed at the cliff; a contiguous majority-AI block failed).
5. **Keep their opening sentence verbatim** — first tokens set the classifier's frame.
6. Tell the user which sentences are theirs vs yours, so later edits don't paraphrase away the human signal.

**Verify with the linter:** run `--mode detector --human <their-draft> <your-output>`. It reports `ai_word_ratio` (must be ≤ ~0.40), `max_consecutive_ai_sentences` (must be < 2 — if it prints 2+, you put two AI sentences back to back), and `opening_is_human` (must be true). These three were pure vibes before; now they're counted.

### Recipe 2 — Discourse fracture (use when only AI text exists)

Validated 2/2 first-try on fresh topics (after 11 failures without it). The text must read as **composed live** — drafted in public, plan abandoned midway — not planned. ALL EIGHT ingredients, not a sample:

1. **One meandering specific story, not an argument.** A single incident with a timeline and named particulars. If each sentence advances a distinct point, it fails no matter how it's dressed — this is the #1 killer. Outline test: if the text can be outlined as tidy bullets, rewrite it. *(Linter can't see this — judgment call.)*
2. **Meta self-interruption** — the writer comments on their own writing and abandons the plan: "i was going to write something structured here but forget it".
3. **Self-correction left visible** — correct a fact mid-text, keep both: "this was february, or march. february."
4. **Repetition as emotion** — same words re-hit because the writer is still angry: "one. per week." / "everywhere. everywhere."
5. **Emotional punctuation** — doubled marks ("!!", "??") at feeling spikes; all-lowercase in casual registers; dropped apostrophes (im, dont, its).
6. **World-vocabulary left raw** — untranslated foreign terms, domain shorthand, local prices/times exactly as the writer's world has them (1,40€, 15h, notaire, kbis).
7. **Unquoted reported dialogue with a name** — "i dont care about the lamination jerome."
8. **End on a self-contradiction the writer notices and leaves in** — "and yes i will buy another one friday. i know." Never a synthesis, never a recap — and never a meaning-tag on the contradiction (see constraint 14).

**Plus these constraints that override everything above — craft kills (learned from a controlled A/B: an 8/8-checklist text still scored 100% AI because it was well-written; the same story flattened passed 100% Human):**

9. **No punchlines.** Fragments must be flat complaints ("my calves by 15h, dead"), never comedy beats. If a line would get a laugh read aloud on stage, it's crafted — rewrite it duller. *(Judgment call — linter can't hear a punchline.)*
10. **No essay skeleton in disguise.** No staged progression ("week one… week two…"), no rhetorical pivot ("you know what actually worked?"), no thesis/moral sentence, no elegant callback ending. If paragraphs have *roles* (setup → experiment → alternative → coda), it's an essay wearing a costume. *(Judgment call; the linter's rule-of-three counter catches only one flavor.)*
11. **Stay under ~160 words.** Every pass was 119–155 words; the 251-word failure gave the classifier twice the evidence. *(Linter counts this.)*
12. **Drop most of the original's points.** Keep 2–3 max; abandon the rest without apology. Full coverage IS the planning fingerprint — a rewrite that converted every essay point into a story beat scored 100% AI. *(Judgment call — you must diff against the source yourself.)*
13. **Entity budget: ≤4 named specifics, and dwell on them.** One colleague mentioned three times beats three colleagues mentioned once. *(Linter estimates distinct named/numbered entities.)*
14. **OBLITERATE significance-marking meta commentary.** Never write a sentence whose only job is to tell the reader what a moment *means*. Banned patterns: "thats the part that got me" · "thats the [uncomfortable/disgusting/weird] part (honestly)" · "what got me was" · "the thing is" · "heres the thing" · "and thats the point" · "which is exactly the problem" · "let that sink in". Field-verified 2026-07-22: a rant passing every other check but containing TWO of these scored 100% AI; deleting exactly those two → 100% Human. A real ranter never announces significance — they repeat the detail or trail off. *(Linter greps the full banned list — this is the single cleanest kill and the linter's highest-value check.)*
15. **Wordbank sweep.** Zero tier-1 hits. At most ONE soft framing adverb (quietly · genuinely · truly · honestly · literally · actually · basically) in the whole piece, never as a sentence-final feeling-tag. *(Linter counts both.)*

**Worked example (this exact text scored 100% Human, High Confidence on Pangram):**

Before (AI draft — scores 100% AI):
> Croissants are, frankly, overrated and even disgusting. The flaky texture that enthusiasts praise is actually a structural disaster, shattering into greasy shards that cling to your clothes and fingers. Each bite delivers an overwhelming amount of butter… Ultimately, the croissant is a triumph of marketing over flavor.

After (discourse fracture — scores 100% Human):
> i know im not supposed to say this but croissants are disgusting. i said it. this was supposed to be a whole review of the boulangerie near my office but forget it, let's talk about the croissant itself. i bought one tuesday, wednesday? tuesday. 1,40€. the outside does its little crunch thing everyone loves and then immediately its raining greasy flakes, on my desk, in my keyboard, everywhere. everywhere. and inside?? air. literally air with butter walls. my colleague says you dont get it, its about the lamination. i dont care about the lamination jerome. the butter sits in your stomach until 15h like a stone. and yes i will buy another one friday. i know.

The After abandoned the argument structure entirely and told one tuesday-croissant story instead. That swap — argument → incident — is the mechanism; the surface mess alone tested at 100% AI.

⚠️ **Do not template off the examples in this file.** In an audit, three independent rewrites all ended with the literal words "i know.", two invented a "marie", two set the incident on "tuesday" — copied straight from this document. Invent fresh names, days, prices, and a fresh plain ending every time; if any exact phrase from this file appears in your output, replace it. (Run the linter, but the linter won't catch borrowed phrasing — you must.)

### Detector-mode self-verify (mechanical + judgment)

**Mechanical — run the linter, paste nothing until it's green on these:**
```
node scripts/tellscan.mjs --mode detector <file>
```
- word count ≤ ~160 · significance-markers = 0 (constraint 14) · soft adverbs ≤ 1 (constraint 15) · tier-1 lexicon = 0 · lowercase register · entity budget ≤ ~4 · (interleave: ratio ≤ 0.40, no 2+ consecutive AI sentences, human opening)

**Judgment — the four the linter cannot see, check by eye every time:**
- [ ] **Story test:** ONE incident, impossible to outline as topic-bullets? Paragraphs with roles (setup/experiment/alternative/coda) or a "you know what actually worked?" pivot → FAIL.
- [ ] **Punchline sweep:** zero lines that perform — flat complaints only.
- [ ] **Coverage test:** at least half the original's points are GONE. List the original's points; if each has a matching story beat, it's a translated essay → cut points.
- [ ] **Ending contradicts the writer's own stance, no recap, no meaning-tag.**

Any ✗ from the linter OR any unchecked judgment box → not done. A text that satisfies the linter but is *well-written* still fails — this is the one rewrite where your instinct to write well is the enemy. Write worse: dwell, repeat, fixate, leave arguments unmade.

### Detector-mode output format

1. The rewritten text, ready to copy.
2. The linter's final output (the ✓/✗ block) — proof the mechanical checks passed, not your say-so.
3. A flag list of **invented specifics** (names, prices, dates you fabricated) — the user must swap in real ones before publishing as their own experience. Never silently present invented facts as real.
4. One line: "Re-test this on the detector — recipes ride the classifier's boundary and detectors retrain." If browser access to the user's detector account is available, offer to test it.

### Hard truths to state when relevant (don't oversell)

- No output is promised detector-proof; the fracture recipe passed 2/2 but detectors update. A green linter is a floor, not a pass.
- Character-level hacks (zero-width chars, homoglyphs) move scores but corrupt text — never apply them; mention only if asked how evasion tools work, with the downsides.
- A discourse-fractured white paper is absurd to a human reader — if the register can't carry a live-rant voice, detector mode needs the interleave protocol (human draft) instead, or the goal isn't reachable.

---

## READER MODE

Target: no *human reader* pegs it as machine-written. Classic de-AI-ing — it will NOT pass statistical detectors (say so if the user might care). Work top-down: structure → sentences → words.

**Audit first — with the linter, not by eye:**
```
node scripts/tellscan.mjs --mode reader <file>
```
It reports tier-1 lexicon hits, em-dash count, tier-2 clustering, negative parallelism, rhetorical Q&A, burstiness (short + long sentence present), and formatting residue. Keep the before-score. Then read `references/tells.md` and `references/wordbank.md` for the constructions the linter flags but can't fully judge (analogy reflex, grandiosity, both-sidesing, suspiciously tidy anecdotes).

**Rewrite, in order:**
1. **Re-architect.** Delete throat-clearing openers and recap conclusions — start where the point starts, end on a specific. Break the intro→3-points→conclusion mold. Cut restatement: AI says everything 1.5 times; say it once.
2. **Restore burstiness.** At least one ≤6-word sentence and one 25+-word sentence; uneven paragraphs; a fragment where it punches; start a sentence with And/But/Because. Max one or two single-sentence paragraphs. *(Linter checks short+long presence and length stdev.)*
3. **Kill constructions on sight** (full list + fixes in `references/tells.md`): "It's not X — it's Y" → say Y. Rule-of-three → best item only. "serves as" → "is". Hedge stacks → commit. "Experts say" → name the source or cut.
4. **Swap the lexicon** per `references/wordbank.md` — the plain spoken word, or a concrete noun from the text's own world.
5. **Ground it in the real.** The strongest single move: numbers, days, names, brands, prices, places, one irrelevant-but-true detail. Placeholders flagged, never silently invented facts.
6. **Punctuation & format.** Em dashes ≤1. Strip emoji bullets, bold-first bullets, title-case headings. Contractions on.
7. **Humanity pass, calibrated to register:** a purposeful comma splice, a parenthetical with attitude, an admission, dry humor, a mild unhedged opinion. At most one or two micro-imperfections, casual registers only. (DETECTOR mode's fracture deliberately exceeds this cap; READER mode does not.)

**Verify.** Re-run `--mode reader`: 0 tier-1 hits, em dashes ≤1, burstiness real. Then the over-scrubbing check the linter can't do: zero tells + zero personality is still AI-shaped — the goal is a voice, not an absence.

**Output:** the rewrite first, then a 3–6 bullet change log (linter tell-count before → after, biggest structural changes, placeholders to replace). No inline annotations, no permission-asking.

---

## Appendix — evidence base (Pangram v3.3.2, tested 2026-07-22)

- **11 pure-AI styled rewrites, all 100% AI High Confidence** — punchy, rambling, lowercase-mess, notes-with-file-paths, literary, keyboard-noise typos, 63-word minimum, ESL rant, idiolect mimicry. No gradient. Style, length, typos, register: not the lever.
- **Discourse fracture: 4/4 passes with the full constraint set** (French-startup deal 155w; croissant 119w; standing-desk 144w; open-plan 141w) — all 100% Human. **Two controlled A/Bs:** a 251-word *crafted* rant (punchlines, staged progression, moral, callback) scored 100% AI; flattened → passed (constraints 9–11). A 141-word rant converting every source point into a beat with a fresh entity per sentence scored 100% AI; dropped to 2 points + ~4 recurring entities → passed (constraints 12–13).
- **Interleave battery on a genuine human draft:** ~13% AI → Human; ~35% → Human; ~45% strictly alternating → Human; ~70% with one contiguous AI block → 100% AI. Levers: ratio ≤ ~40% and no 2+ consecutive AI sentences.
- **Significance-marker isolation test (field):** a rant satisfying the full 13-point recipe scored 100% AI; deleting exactly two significance-marker sentences → 100% Human. The cleanest single-variable result in the base → constraints 14–15. This is why the linter's constraint-14 grep is its highest-value check.
- **Controls:** owner's genuine 2008 blog and hand-written rant → 100% Human.

Interpretation: the classifier keys on planned-text generation dynamics and dominant authorship, not surface style. These thresholds are a snapshot, not a contract — re-test everything. The linter enforces the snapshot's countable floor; it does not replace the detector.
