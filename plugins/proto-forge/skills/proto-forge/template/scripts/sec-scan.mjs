import { execSync } from "node:child_process";
import { ok } from "./lib.mjs";

// BR §4: dependency audit. Hard-stop gate — never auto-suppress.
let failed = false;

try {
  // --prod: the shipped attack surface. Dev-tooling advisories don't reach users
  // and are triaged separately (run `pnpm audit --dev` to see them).
  execSync("pnpm audit --prod --audit-level=high", { stdio: "inherit" });
} catch {
  process.stderr.write("✗ pnpm audit found high/critical advisories in production deps\n");
  failed = true;
}

if (failed) process.exit(1);
ok("sec-scan: no high/critical advisories");
