#!/usr/bin/env node
// .claude/hooks/test-gate.mjs
// Stop hook: runs the suite AND enforces a coverage ratchet (coverage may only
// rise). Blocks on failing tests or dropped line coverage.
import { readFileSync, existsSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
if (input.stop_hook_active) process.exit(0);
const cwd = input.cwd ?? process.cwd();
const has = (f) => existsSync(join(cwd, f));
const BASELINE = join(cwd, ".claude", "coverage-baseline.json");
const TOLERANCE = 0.1; // %, absorbs rounding noise

const sh = (cmd) => execSync(cmd, { cwd, stdio: "pipe", timeout: 600_000 }).toString();
const block = (msg) => { console.error(msg); process.exit(2); };

let coverage = null;
try {
  if (has("Package.swift")) { sh("swift test --enable-code-coverage -q"); coverage = swiftCov(); }
  else if (has("Cargo.toml")) { sh("cargo test -q"); coverage = cargoCov(); }
  else if (has("package.json") && JSON.parse(readFileSync(join(cwd, "package.json"), "utf8")).scripts?.test) {
    sh("npm test --silent"); coverage = jsCov();
  }
  else process.exit(0);
} catch (e) {
  const out = (e.stdout?.toString() ?? "") + (e.stderr?.toString() ?? "");
  block(`TEST GATE FAILED — suite is not green:\n\n${out.slice(-2000)}`);
}

if (coverage != null && Number.isFinite(coverage)) {
  let baseline = 0;
  if (existsSync(BASELINE)) {
    try { baseline = JSON.parse(readFileSync(BASELINE, "utf8")).lines ?? 0; } catch { /* fresh */ }
  }
  if (coverage + TOLERANCE < baseline)
    block(
      `COVERAGE RATCHET FAILED — line coverage dropped.\n` +
      `  baseline ${baseline.toFixed(2)}%  →  current ${coverage.toFixed(2)}%\n` +
      `Add tests for the new code before finishing.`
    );
  if (coverage > baseline)
    writeFileSync(BASELINE, JSON.stringify({ lines: Number(coverage.toFixed(2)) }, null, 2) + "\n");
}
process.exit(0);

function swiftCov() {
  const first = (cmd) => { try { return sh(cmd).trim().split("\n")[0]; } catch { return ""; } };
  const prof = first("find .build -name default.profdata");
  const bin = first("find .build -path '*.xctest/Contents/MacOS/*' -type f");
  if (!prof || !bin) return null;
  const json = sh(
    `xcrun llvm-cov export -summary-only -instr-profile "${prof}" "${bin}" ` +
    `--ignore-filename-regex='\\.build|Tests|checkouts'`
  );
  return JSON.parse(json).data?.[0]?.totals?.lines?.percent ?? null;
}
function cargoCov() {
  try { return JSON.parse(sh("cargo llvm-cov --json --summary-only")).data?.[0]?.totals?.lines?.percent ?? null; }
  catch { return null; } // cargo-llvm-cov not installed → tests still gate, coverage skipped
}
function jsCov() {
  const p = join(cwd, "coverage", "coverage-summary.json");
  if (!existsSync(p)) return null;
  try { return JSON.parse(readFileSync(p, "utf8")).total?.lines?.pct ?? null; } catch { return null; }
}
