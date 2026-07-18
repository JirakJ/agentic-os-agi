# Runbook: vault sync conflict or blocked sync
1. `jj-sync: BLOCKED - gitleaks` -> a secret landed in the vault. Remove it, rewrite the
   note to reference the keychain instead, rerun `bash scripts/jj-sync.sh`.
2. Rebase conflict (rare; union-merge covers append folders): `cd $JJ_VAULT_ROOT`,
   `git status`, resolve by keeping BOTH sides for daily/retro notes, `git rebase --continue`.
3. Diverged machines: `git pull --rebase --autostash` on each, then sync. Never force-push
   the vault.
4. Scheduler dead: macOS `launchctl list | grep jj-sync`; Linux
   `systemctl --user status jj-sync.timer`; Windows `schtasks /Query /TN "jj-agentic-os vault sync"`.
