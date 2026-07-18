# jj-sync.ps1: vault synchronization for Windows (Task Scheduler). Mirrors jj-sync.sh.
$ErrorActionPreference = "Stop"
$Vault = if ($env:JJ_VAULT_ROOT) { $env:JJ_VAULT_ROOT } else { Join-Path $env:USERPROFILE "jj-vault" }
if (-not (Test-Path (Join-Path $Vault ".git"))) { Write-Error "jj-sync: $Vault is not a git repo"; exit 1 }
Set-Location $Vault
git pull --rebase --autostash --quiet; if ($LASTEXITCODE -ne 0) { Write-Warning "jj-sync: pull failed (offline?)" }
if (-not (git status --porcelain)) { exit 0 }
git add -A
if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
  gitleaks git --staged --no-banner --redact -v
  if ($LASTEXITCODE -ne 0) { git reset --quiet; Write-Error "jj-sync: BLOCKED - secrets in vault delta"; exit 1 }
}
git commit --quiet -m "chore(vault): sync $env:COMPUTERNAME $(Get-Date -Format o -AsUTC)"
git push --quiet; if ($LASTEXITCODE -ne 0) { Write-Warning "jj-sync: push failed (offline?) - retry next run" }
