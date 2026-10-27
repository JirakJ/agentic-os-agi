#!/usr/bin/env node
// tellscan — deterministic scorer for the anti-ai skill.
// The skill's own self-verify is a hand-count ("Count, literally"; "Grep the draft
// literally for…"). A model grading its own output is the weak link. This computes
// the countable checks mechanically so the verdict isn't self-reported.
//
// It scores READER tells (Pangram-invariant, reader-facing) and the DETECTOR-mode
// checklist (discourse fracture / interleave). It does NOT and CANNOT predict a
// statistical detector's verdict — no local tool can. It removes the dishonesty in
// the checklist step, nothing more. Re-test on the real detector; recipes ride the
// classifier boundary.
//
// Usage:
//   node tellscan.mjs <file>                         # auto (reader audit + detector checklist)
//   node tellscan.mjs --mode reader <file>
//   node tellscan.mjs --mode detector <file>
//   node tellscan.mjs --mode detector --human draft.txt out.txt   # interleave metrics
//   cat text | node tellscan.mjs -                   # stdin
//   node tellscan.mjs --json <file>                  # machine output
//   node tellscan.mjs --selftest
//
// stdlib only. Exit 0 always for reader mode; exit 1 in detector mode when the
// checklist is not met (so it can gate a CI step); --json never changes exit code.

import { readFileSync } from "node:fs";

const emit = (s) => process.stdout.write(s + "\n");

// ---- reference data (mirrors references/wordbank.md; keep in sync) ----
const TIER1 = [
  "delve","leverage","underscore","harness","foster","utilize","facilitate","streamline",
  "bolster","illuminate","showcase","embark","elevate","empower","unleash","uncover",
  "optimize","garner","resonate","revolutionize","synthesize","elucidate","transcend",
  "reimagine","intertwine","entwine","espouse","exemplify","underpin",
  "tapestry","realm","ecosystem","paradigm","synergy","testament","beacon","interplay",
  "intricacies","kaleidoscope","whimsy","endeavor","myriad","plethora","advancements",
  "pivotal","crucial","seamless","seamlessly","robust","vibrant","intricate","meticulous",
  "meticulously","nuanced","cutting-edge","transformative","game-changing","groundbreaking",
  "unparalleled","invaluable","multifaceted","commendable","indelible","poignant","profound",
  "profoundly","relentless","relentlessly","tireless","tirelessly","unwavering","unyielding",
  "timeless","ever-evolving","fast-paced",
];
const TIER1_PHRASES = [
  "in today's fast-paced world","in today's fast-paced landscape","it's important to note",
  "it is worth noting","plays a pivotal role","plays a crucial role","stands as a testament to",
  "rich tapestry","navigate the complexities of","in conclusion","in summary","at its core",
  "that being said","a key takeaway","paving the way for","valuable insights","deeper understanding of",
  "shed light on","when it comes to","not only","here's the kicker","here's the thing","the best part",
  "i hope this email finds you well","look no further","dive into","deep-dive into","let's explore",
  "let's unpack","let's break down",
];
const TIER2 = [
  "comprehensive","significant","significantly","essential","critical","dynamic","innovative",
  "powerful","notable","notably","vital","vast","explore","enhance","ensure","highlight","reveal",
  "engage","embrace","insights","perspective","framework","approach","strategy","challenges",
  "opportunities","potential","impactful","genuinely","truly","remarkably","arguably","thought-provoking",
  "resilience","perseverance","dedication","sustainable","sustainability",
];
// constraint 14 — significance-marking meta commentary. The single cleanest detector kill.
const SIG_MARKERS = [
  "the part that got me","the part that gets me","thats the part","that's the part",
  "the disgusting part","the uncomfortable part","the weird part","the funny part","the sad part",
  "what got me was","what got me is","what kills me","what gets me","the thing is","here's the thing",
  "heres the thing","and thats the point","and that's the point","which is exactly the problem",
  "which is exactly the point","let that sink in","thats what kills me","that's what kills me",
  "thats the point","that's the point",
];
// soft framing adverbs (constraint 15) — at most one, never as a feeling-tag
const SOFT_ADVERBS = ["quietly","genuinely","truly","honestly","literally","actually","basically"];

// ---- helpers ----
const norm = (s) => s.toLowerCase();
const sentences = (t) =>
  t.replace(/\s+/g, " ").match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [];
const words = (t) => (t.toLowerCase().match(/[a-z0-9'’-]+/g) ?? []);
// count word-boundary occurrences of a term (term may be multiword phrase)
function countTerm(text, term) {
  const t = norm(text);
  if (term.includes(" ")) {
    let n = 0, i = 0;
    while ((i = t.indexOf(term, i)) !== -1) { n++; i += term.length; }
    return n;
  }
  const re = new RegExp(`(?<![a-z0-9])${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![a-z0-9])`, "g");
  return (t.match(re) ?? []).length;
}

function scan(text, human) {
  const S = sentences(text);
  const W = words(text);
  const wc = W.length;

  // lexicon
  const tier1 = [];
  for (const w of TIER1) { const n = countTerm(text, w); if (n) tier1.push([w, n]); }
  for (const p of TIER1_PHRASES) { const n = countTerm(text, p); if (n) tier1.push([p, n]); }
  const tier2Hits = TIER2.map((w) => [w, countTerm(text, w)]).filter(([, n]) => n);
  const tier2Total = tier2Hits.reduce((a, [, n]) => a + n, 0);
  // tier2 cluster: >=2 in one sentence, or >=5 in whole piece
  const clusterSentences = S.filter((s) => TIER2.reduce((a, w) => a + countTerm(s, w), 0) >= 2).length;

  // significance markers (constraint 14)
  const sig = SIG_MARKERS.map((p) => [p, countTerm(text, p)]).filter(([, n]) => n);
  const sigTotal = sig.reduce((a, [, n]) => a + n, 0);

  // soft adverbs
  const soft = SOFT_ADVERBS.map((w) => [w, countTerm(text, w)]).filter(([, n]) => n);
  const softTotal = soft.reduce((a, [, n]) => a + n, 0);

  // punctuation
  const emDash = (text.match(/—/g) ?? []).length + (text.match(/(?<=\S) ?-- ?(?=\S)/g) ?? []).length;
  const doubledPunct = (text.match(/[!?]{2,}/g) ?? []).length;
  const oxford = (text.match(/,\s+(?:and|or)\s+/gi) ?? []).length;

  // constructions (heuristic regex — flags, not proofs)
  const negParallel =
    (text.match(/\bit'?s not\b[^.?!]*\bit'?s\b/gi) ?? []).length +
    (text.match(/\bnot just\b[^.?!]*\bbut\b/gi) ?? []).length +
    (text.match(/\bthe question is(?:n'?t| not)\b/gi) ?? []).length;
  const ruleOfThree = (text.match(/\b[\w-]+,\s+[\w-]+,\s+and\s+[\w-]+\b/g) ?? []).length;
  const rhetoricalQA = (text.match(/\b(the result|why|the best part|here'?s the kicker)\?/gi) ?? []).length;

  // formatting residue
  const boldBullets = (text.match(/^\s*[-*]\s*\*\*/gm) ?? []).length;
  const emojiBullets = (text.match(/^\s*(?:[✅🔹🧠➡️→•]|[✀-➿]|[\u{1f300}-\u{1faff}])/gmu) ?? []).length;
  const mdResidue = (text.match(/\*\*|^#{1,6}\s|\]\(https?:/gm) ?? []).length;

  // burstiness
  const lens = S.map((s) => words(s).length).filter((n) => n > 0);
  const mean = lens.reduce((a, b) => a + b, 0) / (lens.length || 1);
  const stdev = Math.sqrt(lens.reduce((a, b) => a + (b - mean) ** 2, 0) / (lens.length || 1));
  const hasShort = lens.some((n) => n <= 6);
  const hasLong = lens.some((n) => n >= 25);

  // casual-register signals (detector mode)
  const letters = (text.match(/[a-zA-Z]/g) ?? []).length;
  const upper = (text.match(/[A-Z]/g) ?? []).length;
  const upperRatio = letters ? upper / letters : 0; // low => lowercase register
  const droppedApos = countTerm(text, "im") + countTerm(text, "dont") + countTerm(text, "cant") +
    countTerm(text, "its") + countTerm(text, "thats") + countTerm(text, "youre");

  // entity budget (detector constraint 13): distinct capitalized tokens + distinct numbers
  const caps = new Set((text.match(/(?<![.!?…]\s)(?<!^)\b[A-Z][a-z]{2,}\b/gm) ?? []).map((s) => s.toLowerCase()));
  const nums = new Set(text.match(/\d[\d.,]*/g) ?? []);
  const entityEstimate = caps.size + nums.size;

  // interleave metrics (only when a human base draft is supplied)
  let interleave = null;
  if (human != null) {
    const hSet = new Set(sentences(human).map((s) => s.toLowerCase().replace(/\s+/g, " ").trim()));
    const flags = S.map((s) => hSet.has(s.toLowerCase().replace(/\s+/g, " ").trim())); // true=human
    let aiWords = 0, humanWords = 0, run = 0, maxRun = 0;
    S.forEach((s, i) => {
      const n = words(s).length;
      if (flags[i]) { humanWords += n; run = 0; }
      else { aiWords += n; run++; maxRun = Math.max(maxRun, run); }
    });
    interleave = {
      ai_word_ratio: +(aiWords / (aiWords + humanWords || 1)).toFixed(3),
      max_consecutive_ai_sentences: maxRun,
      opening_is_human: flags[0] === true,
      human_sentences: flags.filter(Boolean).length,
      ai_sentences: flags.filter((f) => !f).length,
    };
  }

  return {
    word_count: wc, sentence_count: S.length,
    tier1, tier1_total: tier1.reduce((a, [, n]) => a + n, 0),
    tier2_total: tier2Total, tier2_cluster_sentences: clusterSentences,
    significance_markers: sig, significance_total: sigTotal,
    soft_adverbs: soft, soft_total: softTotal,
    em_dash: emDash, doubled_punct: doubledPunct, oxford_commas: oxford,
    neg_parallelism: negParallel, rule_of_three: ruleOfThree, rhetorical_qa: rhetoricalQA,
    bold_bullets: boldBullets, emoji_bullets: emojiBullets, markdown_residue: mdResidue,
    sentence_len_stdev: +stdev.toFixed(2), has_short_sentence: hasShort, has_long_sentence: hasLong,
    upper_ratio: +upperRatio.toFixed(3), dropped_apostrophes: droppedApos,
    entity_estimate: entityEstimate,
    interleave,
  };
}

// ---- verdicts ----
function readerChecklist(m) {
  const c = [];
  c.push(["tier1 lexicon = 0", m.tier1_total === 0, `${m.tier1_total} hit(s): ${m.tier1.map(([w, n]) => `${w}×${n}`).join(", ")}`]);
  c.push(["em dashes ≤ 1", m.em_dash <= 1, `${m.em_dash}`]);
  c.push(["tier2 not clustered", m.tier2_cluster_sentences === 0 && m.tier2_total <= 5, `${m.tier2_total} total, ${m.tier2_cluster_sentences} clustered sentence(s)`]);
  c.push(["no negative parallelism", m.neg_parallelism === 0, `${m.neg_parallelism}`]);
  c.push(["no rhetorical Q&A drumroll", m.rhetorical_qa === 0, `${m.rhetorical_qa}`]);
  c.push(["burstiness (short + long sentence present)", m.has_short_sentence && m.has_long_sentence, `stdev ${m.sentence_len_stdev}, short:${m.has_short_sentence} long:${m.has_long_sentence}`]);
  c.push(["no emoji/bold bullets", m.emoji_bullets === 0 && m.bold_bullets === 0, `emoji:${m.emoji_bullets} bold:${m.bold_bullets}`]);
  c.push(["no markdown residue", m.markdown_residue === 0, `${m.markdown_residue}`]);
  return c;
}
function detectorChecklist(m) {
  const c = [];
  c.push(["word count ≤ ~160", m.word_count <= 160, `${m.word_count}`]);
  c.push(["ZERO significance-markers (constraint 14)", m.significance_total === 0, m.significance_markers.map(([p]) => `"${p}"`).join(", ") || "clean"]);
  c.push(["≤1 soft framing adverb (constraint 15)", m.soft_total <= 1, `${m.soft_total}: ${m.soft_adverbs.map(([w, n]) => `${w}×${n}`).join(", ")}`]);
  c.push(["tier1 lexicon = 0", m.tier1_total === 0, `${m.tier1_total}`]);
  c.push(["≥2 emotional-punctuation moments (!!/??)", m.doubled_punct >= 2, `${m.doubled_punct}`]);
  c.push(["lowercase register (upper ratio < ~0.03)", m.upper_ratio < 0.03, `${m.upper_ratio}`]);
  c.push(["entity budget ≤ ~4 (constraint 13)", m.entity_estimate <= 4, `~${m.entity_estimate} distinct named/numbered`]);
  c.push(["no essay skeleton (no rule-of-three chains)", m.rule_of_three <= 1, `${m.rule_of_three}`]);
  if (m.interleave) {
    const iv = m.interleave;
    c.push(["interleave: AI word ratio ≤ ~0.40", iv.ai_word_ratio <= 0.40, `${iv.ai_word_ratio}`]);
    c.push(["interleave: no 2+ consecutive AI sentences", iv.max_consecutive_ai_sentences < 2, `max run ${iv.max_consecutive_ai_sentences}`]);
    c.push(["interleave: opening sentence is human", iv.opening_is_human, `${iv.opening_is_human}`]);
  }
  return c;
}

function render(m, mode) {
  const out = [];
  const line = (label, ok, detail) => `  ${ok ? "✓" : "✗"} ${label}${detail ? `  — ${detail}` : ""}`;
  if (mode === "reader" || mode === "auto") {
    const c = readerChecklist(m);
    const pass = c.filter(([, ok]) => ok).length;
    out.push(`READER audit — ${pass}/${c.length} tells clear`);
    c.forEach(([l, ok, d]) => out.push(line(l, ok, d)));
  }
  if (mode === "detector" || mode === "auto") {
    const c = detectorChecklist(m);
    const pass = c.filter(([, ok]) => ok).length;
    if (out.length) out.push("");
    out.push(`DETECTOR checklist — ${pass}/${c.length} met  (machine-countable subset; re-test on the real detector)`);
    c.forEach(([l, ok, d]) => out.push(line(l, ok, d)));
  }
  out.push("", `words ${m.word_count} · sentences ${m.sentence_count} · len-stdev ${m.sentence_len_stdev} · em-dash ${m.em_dash}`);
  return out.join("\n");
}

// ---- selftest ----
function selftest() {
  const assert = (c, msg) => { if (!c) throw new Error("selftest: " + msg); };
  const ai = "In today's fast-paced world, we must leverage robust, scalable, and seamless synergy. It's not about tools — it's about mindset. The result? Transformative.";
  const a = scan(ai);
  assert(a.tier1_total >= 3, "tier1 should fire on ai text");
  assert(a.em_dash === 1, "one em dash, got " + a.em_dash);
  assert(a.neg_parallelism >= 1, "neg parallelism missed");
  assert(a.rhetorical_qa >= 1, "rhetorical QA missed");
  assert(a.rule_of_three >= 1, "rule of three missed");
  assert(readerChecklist(a).filter(([, ok]) => ok).length < 6, "ai text should fail several reader checks");

  const human = "i bought a croissant tuesday. 1,40€. it rained flakes everywhere.";
  const humanScan = scan(human);
  assert(humanScan.tier1_total === 0, "clean human text should have no tier1");

  // significance markers
  const sig = scan("i was mad. thats the part that got me. honestly.");
  assert(sig.significance_total >= 1, "significance marker missed");
  assert(sig.soft_total >= 1, "soft adverb honestly missed");

  // interleave
  const draft = "i hate mondays. the coffee was cold.";
  const mixed = "i hate mondays. This is a fully machine written sentence added between. the coffee was cold.";
  const iv = scan(mixed, draft).interleave;
  assert(iv.opening_is_human === true, "opening should be human");
  assert(iv.max_consecutive_ai_sentences === 1, "one AI sentence run, got " + iv.max_consecutive_ai_sentences);
  assert(iv.ai_word_ratio > 0 && iv.ai_word_ratio < 0.6, "ratio sane, got " + iv.ai_word_ratio);

  // doubled punctuation + lowercase register
  const rant = scan("air?? literally air with butter walls. everywhere. everywhere.");
  assert(rant.doubled_punct >= 1, "doubled punct missed");
  assert(rant.upper_ratio < 0.03, "lowercase register misread");

  emit("selftest: OK");
}

// ---- cli ----
function main() {
  const argv = process.argv.slice(2);
  if (argv.includes("--selftest")) return selftest();
  let mode = "auto", json = false, humanPath = null, file = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--mode") mode = argv[++i];
    else if (a === "--json") json = true;
    else if (a === "--human") humanPath = argv[++i];
    else file = a;
  }
  const text = file && file !== "-" ? readFileSync(file, "utf8") : readFileSync(0, "utf8");
  const human = humanPath ? readFileSync(humanPath, "utf8") : null;
  const m = scan(text, human);
  if (json) { emit(JSON.stringify(m, null, 2)); return; }
  emit(render(m, mode));
  // exit 1 in detector mode when checklist unmet — lets a CI step gate on it
  if (mode === "detector") {
    const unmet = detectorChecklist(m).some(([, ok]) => !ok);
    process.exit(unmet ? 1 : 0);
  }
}
main();
