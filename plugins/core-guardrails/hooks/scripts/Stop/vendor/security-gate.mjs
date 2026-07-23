#!/usr/bin/env node
// .claude/hooks/security-gate.mjs
// Stop hook: aggregates secret-scan (gitleaks) + SAST (semgrep) + dependency
// audit (osv-scanner). Blocks completion until the working tree is clean.
import { readFileSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";

const input = JSON.parse(readFileSync(0, "utf8"));
if (input.stop_hook_active) process.exit(0);
const cwd = input.cwd ?? process.cwd();

const findings = [];
const missing = [];

const run = (cmd) => execSync(cmd, { cwd, stdio: "pipe", timeout: 240_000, maxBuffer: 64 * 1024 * 1024 }).toString();
const tool = (bin) => {
  try { execSync(`command -v ${bin}`, { stdio: "pipe" }); return true; } catch { return false; }
};

// 1) Secrets — gitleaks over the working tree (incl. untracked files).
//    Scan by ABSOLUTE path: with `dir .` the reported paths are cwd-relative,
//    so the "(^|/)\.claude/worktrees/" allowlist in gitleaks.toml can never
//    match when the session runs inside a worktree.
if (tool("gitleaks")) {
  try {
    run(`gitleaks dir "${cwd}" --no-banner --redact -v --config "${import.meta.dirname}/gitleaks.toml"`);
  } catch (e) {
    const out = (e.stdout?.toString() ?? "") + (e.stderr?.toString() ?? "");
    if (e.status === 1 || /leaks? found|finding/i.test(out))
      findings.push(`SECRETS (gitleaks):\n${out.slice(-1200)}`);
  }
} else missing.push("gitleaks      brew install gitleaks");

// 2) SAST — semgrep, error-severity only (drop WARNING to avoid noise).
//    For private/enterprise code, swap --config auto for a local ruleset
//    (e.g. --config p/security-audit) so no metadata leaves the machine.
//    Same worktree principle as the gitleaks allowlist: a Claude Code worktree
//    is a copy of the canonical tree, so pre-existing findings belong to the
//    main checkout. Inside a worktree scan only what this branch touched
//    (diff vs merge-base + untracked); full scan otherwise.
let semgrepTargets = ""; // "" = full scan
if (cwd.includes("/.claude/worktrees/")) {
  try {
    const base = run("git merge-base HEAD main 2>/dev/null || git merge-base HEAD master").trim();
    const changed = [...new Set(
      (run(`git diff --name-only ${base}`) + run("git ls-files --others --exclude-standard"))
        .split("\n").map((s) => s.trim()).filter(Boolean)
    )].filter((f) => existsSync(`${cwd}/${f}`));
    semgrepTargets = changed.length ? changed.map((f) => `"${f}"`).join(" ") : null; // null = nothing new
  } catch { /* merge-base unavailable — fall back to full scan */ }
}
if (tool("semgrep") && semgrepTargets !== null) {
  try {
    const json = run(`semgrep scan --quiet --severity ERROR --json --config auto ${semgrepTargets}`);
    const res = JSON.parse(json).results ?? [];
    if (res.length) {
      const lines = res.slice(0, 15)
        .map((r) => `  ${r.check_id} @ ${r.path}:${r.start?.line}`).join("\n");
      findings.push(`SAST (semgrep) — ${res.length} ERROR finding(s):\n${lines}`);
    }
  } catch (e) {
    try {
      const res = JSON.parse(e.stdout?.toString() ?? "{}").results ?? [];
      if (res.length) findings.push(`SAST (semgrep) — ${res.length} ERROR finding(s)`);
    } catch { /* internal semgrep error, non-blocking */ }
  }
} else missing.push("semgrep       brew install semgrep");

// 3) Vulnerable deps — osv-scanner across all lockfiles (npm, Cargo, SwiftPM, pip).
if (tool("osv-scanner")) {
  try {
    run("osv-scanner scan source -r --format=json .");
  } catch (e) {
    try {
      const r = JSON.parse(e.stdout?.toString() ?? "{}");
      const vulns = (r.results ?? [])
        .flatMap((x) => x.packages ?? [])
        .flatMap((p) => (p.vulnerabilities ?? [])
          .map((v) => `  ${p.package?.name}@${p.package?.version}: ${v.id} (${sev(v)})`));
      if (vulns.length)
        findings.push(`VULNERABLE DEPS (osv-scanner):\n${vulns.slice(0, 20).join("\n")}`);
    } catch { /* no JSON payload */ }
  }
} else missing.push("osv-scanner   brew install osv-scanner");

function sev(v) {
  return v.database_specific?.severity ?? v.severity?.[0]?.score ?? "unknown";
}

if (findings.length) {
  console.error(
    `SECURITY GATE FAILED — resolve before finishing:\n\n${findings.join("\n\n")}` +
    (missing.length ? `\n\n(skipped, not installed: ${missing.map((m) => m.split(" ")[0]).join(", ")})` : "")
  );
  process.exit(2);
}
if (missing.length) console.error(`Security scanners not installed:\n  ${missing.join("\n  ")}`);
process.exit(0);
