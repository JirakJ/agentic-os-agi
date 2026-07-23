#!/usr/bin/env node
// .claude/hooks/i18n-complete.mjs
// PostToolUse(Write|Edit) + Stop: fails on INCOMPLETE translations.
// - .xcstrings: every translatable key must be "translated" in every locale
//   present in the catalog (plurals/device variations included).
// - locales/*.json: key sets must match the richest reference locale; no empty values.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, basename, join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
const event = input.hook_event_name;
const cwd = input.cwd ?? process.cwd();

const errors = [];
const warnings = [];

for (const file of collectTargets()) {
  if (file.endsWith(".xcstrings")) checkXcstrings(file);
  else if (file.endsWith(".json")) checkJsonLocale(file);
}

if (errors.length) {
  console.error(
    `TRANSLATION GATE FAILED — incomplete localization:\n\n` +
    errors.slice(0, 40).join("\n") +
    (errors.length > 40 ? `\n…and ${errors.length - 40} more` : "") +
    (warnings.length ? `\n\nNeeds review (not blocking):\n${warnings.slice(0, 10).join("\n")}` : "")
  );
  process.exit(2);
}
if (warnings.length) console.error(`Translations need review:\n${warnings.slice(0, 10).join("\n")}`);
process.exit(0);

function collectTargets() {
  if (event === "Stop") return walk(cwd, /\.xcstrings$/);
  const p = input.tool_input?.file_path;
  if (!p) return [];
  if (p.endsWith(".xcstrings")) return [p];
  if (p.endsWith(".json") && /(^|\/)(locales?|i18n|lang)(\/|$)/i.test(p))
    return readdirSync(dirname(p)).filter((f) => f.endsWith(".json")).map((f) => join(dirname(p), f));
  return [];
}

// ---- Apple String Catalog ----
function checkXcstrings(path) {
  let cat;
  try { cat = JSON.parse(readFileSync(path, "utf8")); }
  catch { errors.push(`${rel(path)}: invalid JSON`); return; }

  const source = cat.sourceLanguage;
  const strings = cat.strings ?? {};
  const langs = new Set([source]);
  for (const e of Object.values(strings))
    for (const l of Object.keys(e.localizations ?? {})) langs.add(l);

  for (const [key, entry] of Object.entries(strings)) {
    if (entry.shouldTranslate === false) continue;
    const locs = entry.localizations ?? {};
    for (const lang of langs) {
      if (lang === source && !locs[lang]) continue; // source defaults to the key text
      const loc = locs[lang];
      if (!loc) { errors.push(`${rel(path)} :: "${key}" → missing [${lang}]`); continue; }
      for (const u of units(loc)) {
        const empty = !u.value || !u.value.trim();
        if (u.state === "new" || u.state === "stale" || empty)
          errors.push(`${rel(path)} :: "${key}" [${lang}]${u.ctx} → ${u.state || "empty"}`);
        else if (u.state === "needs_review")
          warnings.push(`${rel(path)} :: "${key}" [${lang}]${u.ctx}`);
      }
    }
  }
}

function units(loc) {
  const out = [];
  if (loc.stringUnit) out.push({ ...loc.stringUnit, ctx: "" });
  if (loc.variations) walkVar(loc.variations, out, "");
  if (!loc.stringUnit && !loc.variations) out.push({ state: "new", value: "", ctx: "" });
  return out;
}
function walkVar(v, out, prefix) {
  for (const [kind, cases] of Object.entries(v))
    for (const [name, node] of Object.entries(cases)) {
      const ctx = ` ${prefix}${kind}.${name}`;
      if (node.stringUnit) out.push({ ...node.stringUnit, ctx });
      if (node.variations) walkVar(node.variations, out, `${prefix}${kind}.${name} `);
    }
}

// ---- Web JSON locales ----
function checkJsonLocale(path) {
  const dir = dirname(path);
  const files = readdirSync(dir).filter((f) => f.endsWith(".json"));
  if (files.length < 2) return;
  const maps = files.map((f) => ({ f, map: flatten(safeLoad(join(dir, f))) }));
  const ref = maps.reduce((a, b) => (b.map.size > a.map.size ? b : a));
  const me = maps.find((m) => m.f === basename(path));
  if (!me || me.f === ref.f) return;
  for (const k of ref.map.keys())
    if (!me.map.has(k)) errors.push(`${rel(path)} → missing key "${k}" (in ${ref.f})`);
  for (const [k, val] of me.map)
    if (val == null || !String(val).trim()) errors.push(`${rel(path)} → empty value "${k}"`);
}

// ---- utils ----
function safeLoad(p) { try { return JSON.parse(readFileSync(p, "utf8")); } catch { return {}; } }
function flatten(obj, prefix = "", out = new Map()) {
  for (const [k, v] of Object.entries(obj ?? {})) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, key, out);
    else out.set(key, v);
  }
  return out;
}
function rel(p) { return p.startsWith(cwd) ? p.slice(cwd.length + 1) : p; }
function walk(dir, rx, acc = []) {
  let entries;
  try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return acc; }
  for (const e of entries) {
    if (e.name.startsWith(".")) continue;
    if (["node_modules", ".build", "DerivedData", "Pods", "dist", "build"].includes(e.name)) continue;
    const full = join(dir, e.name);
    if (e.isDirectory()) walk(full, rx, acc);
    else if (rx.test(e.name)) acc.push(full);
  }
  return acc;
}
