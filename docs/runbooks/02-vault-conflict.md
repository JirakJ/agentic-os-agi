# Runbook: vault sync conflict or blocked sync
1. Rebase conflict (rare; union-merge covers append folders): `cd $JJ_VAULT_ROOT`,
   `git status`, resolve by keeping BOTH sides for daily/retro notes, `git rebase --continue`.
2. Diverged machines: `git pull --rebase --autostash` on each, then sync. Never force-push
   the vault.
3. Scheduler dead: macOS `launchctl list | grep jj-sync`; Linux
   `systemctl --user status jj-sync.timer`; Windows `schtasks /Query /TN "jj-agentic-os vault sync"`.
