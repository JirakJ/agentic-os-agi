---
name: jetbrains-release
description: Ship a JetBrains plugin release end-to-end in lockstep - version bump, plugin.xml change-notes, README, buildPlugin + verifyPlugin, tag, and Marketplace upload. Use whenever the user mentions JetBrains plugin release, Marketplace, plugin.xml, change-notes, verifyPlugin, or wants to publish/update any of their IDE plugins.
license: MIT
metadata:
  version: "3.0.0"
---

# JetBrains Plugin Release

Non-negotiable: code, docs, `plugin.xml` change-notes, and the Marketplace listing never
drift apart. One release = one atomic commit + tag + upload.

## Procedure
1. Preconditions: working tree clean, `scripts/preflight.sh` green (project_type
   `jetbrains-plugin` runs `buildPlugin verifyPlugin` as smoke).
2. Choose SemVer bump from the change set (fix=patch, feature=minor, breaking=major).
3. Lockstep edit in ONE change: `gradle.properties`/build version, `plugin.xml`
   `<change-notes>` (user-facing, newest release only, HTML-safe), README feature list,
   CHANGELOG entry.
4. Verify: `./gradlew clean buildPlugin verifyPlugin` - zero verifier warnings allowed for
   `until-build` compatibility; fix compatibility ranges, do not suppress.
5. Commit `chore(release): vX.Y.Z - <summary>` (passes the commit-integrity gate), tag
   `vX.Y.Z`, push with `--follow-tags`.
6. Upload: `./gradlew publishPlugin` with `PUBLISH_TOKEN` from the environment (never
   inline the token; security-gate will deny attempts to read token files).
7. Post-release: confirm the Marketplace version went live; log the release in the vault
   project MOC; if this is one of many plugins, repeat per plugin - never batch-skip
   verifyPlugin.

## Validation
- verifyPlugin clean, tag pushed, Marketplace shows X.Y.Z, change-notes rendered correctly.
