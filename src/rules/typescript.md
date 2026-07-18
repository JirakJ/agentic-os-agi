---
applyTo: "**/*.ts,**/*.tsx"
description: "TypeScript conventions"
---
- Strict TypeScript (`"strict": true`); `tsc --noEmit` and `eslint --max-warnings=0` clean
  before commit. No `any` without a justifying comment.
- Frozen lockfile installs only (`pnpm install --frozen-lockfile` / `npm ci`).
- Current stable runtime and framework versions; no deprecated APIs.
