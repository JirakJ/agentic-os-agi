# Runbook: roll back a bad distribution release
1. Identify last good tag: `git tag --sort=-creatordate | head`.
2. `git revert` the release commit (keeps history; lockstep files revert together), or for
   a broken tag only: fix forward with a patch release via `scripts/release.sh X.Y.Z+1`.
3. Re-run `bash scripts/validate-all.sh`; push with `--follow-tags`.
4. Claude Code users: `/plugin marketplace update jj-agentic-os` then reinstall plugins.
5. Copilot repos consuming the template: regenerate via bootstrap --target-repo after the fix.
