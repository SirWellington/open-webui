# Wellington sync helper (PowerShell)
#
# Purpose: rebase the `wellington` branch onto the latest upstream/main so the
# fork tracks open-webui/open-webui while keeping the Wellington customizations.
#
# Safety: this script is NON-DESTRUCTIVE. It will NOT force-push, drop commits,
# or reset. It refuses to run on a dirty working tree unless you pass -Force
# (which only stashes, and restores the stash afterward).
#
# Usage (from the repo root OR from wellington/):
#   .\wellington\sync.ps1            # show status + fetch (no rebase)
#   .\wellington\sync.ps1 -Rebase    # fetch + rebase onto upstream/main
#   .\wellington\sync.ps1 -Rebase -Force   # allow a dirty tree (auto stash/restore)
#
# Requires: git on PATH. Run with PowerShell 5.1+.

[CmdletBinding()]
param(
    [switch]$Rebase,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Resolve the repo root (this script lives in <root>/wellington/).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
Push-Location $RepoRoot
try {
    # --- Sanity: are we in a git repo with the expected remotes? ---
    $isRepo = (& git rev-parse --is-inside-work-tree 2>$null) -eq 'true'
    if (-not $isRepo) { throw "Not inside a git repository at: $RepoRoot" }

    $remotes = & git remote
    if ($remotes -notcontains 'upstream') {
        throw "Missing 'upstream' remote. Add it with:`n  git remote add upstream https://github.com/open-webui/open-webui.git"
    }

    Write-Host "`n=== Wellington sync ===" -ForegroundColor Cyan
    Write-Host ("Repo root : " + $RepoRoot)
    Write-Host ("Branch    : " + (& git rev-parse --abbrev-ref HEAD))

    # --- Working tree check ---
    $status = & git status --porcelain
    $dirty  = @($status | Where-Object { $_ -ne '' }).Count
    $stashed = $false
    if ($dirty -gt 0) {
        if (-not $Force) {
            Write-Host "`nWorking tree has $dirty uncommitted change(s):" -ForegroundColor Yellow
            & git status --short
            Write-Host "`nCommit or stash them first, then re-run with -Rebase." -ForegroundColor Yellow
            Write-Host "Or re-run with -Force to let this script stash/restore them." -ForegroundColor Yellow
            return
        } else {
            Write-Host "`nStashing $dirty uncommitted change(s) (will restore after)..." -ForegroundColor Yellow
            & git stash push -u -m "wellington-sync-autostash"
            $stashed = $true
        }
    }

    if (-not $Rebase) {
        # Status-only mode: fetch and report.
        Write-Host "`nFetching upstream..." -ForegroundColor Cyan
        & git fetch --all --prune
        $counts = & git rev-list --left-right --count upstream/main...HEAD
        $behind = ($counts[0] -split '\s+')[-1]
        $ahead  = ($counts[1] -split '\s+')[-1]
        Write-Host ("Behind upstream/main : " + $behind)
        Write-Host ("Ahead  of upstream/main: " + $ahead)
        if ($behind -eq '0') {
            Write-Host "`nAlready up to date with upstream/main. Nothing to rebase." -ForegroundColor Green
        } else {
            Write-Host "`n$behind new upstream commit(s). Re-run with -Rebase to rebase." -ForegroundColor Green
        }
        return
    }

    # --- Rebase mode ---
    Write-Host "`nFetching upstream..." -ForegroundColor Cyan
    & git fetch --all --prune

    $counts = & git rev-list --left-right --count upstream/main...HEAD
    $behind = ($counts[0] -split '\s+')[-1]
    if ($behind -eq '0') {
        Write-Host "`nAlready up to date with upstream/main. Nothing to rebase." -ForegroundColor Green
        if ($stashed) { & git stash pop }
        return
    }

    # Known conflict-surface files (modified relative to upstream). Listed so the
    # user knows what to expect if the rebase stops on conflicts.
    $conflictSurface = @(
        'Dockerfile'
        'backend/open_webui/models/automations.py'
        'backend/open_webui/routers/tasks.py'
        'backend/open_webui/utils/automations.py'
        'backend/open_webui/utils/middleware.py'
        'src/lib/apis/automations/index.ts'
        'src/lib/components/AutomationModal.svelte'
        'src/lib/components/automations/AutomationEditor.svelte'
        'src/lib/components/automations/ChatTargetDropdown.svelte'
        'src/lib/components/common/Select.svelte'
        'src/lib/components/layout/Sidebar/ChatItem.svelte'
        'src/lib/i18n/locales/en-US/translation.json'
    )

    Write-Host "`nRebasing onto upstream/main ($behind upstream commit(s))..." -ForegroundColor Cyan
    Write-Host ("Files you have modified that MAY conflict:") -ForegroundColor DarkGray
    $conflictSurface | ForEach-Object { Write-Host ("  - " + $_) -ForegroundColor DarkGray }
    Write-Host ""

    & git rebase upstream/main
    $rc = $LASTEXITCODE

    if ($rc -eq 0) {
        Write-Host "`nRebase succeeded." -ForegroundColor Green
    } else {
        Write-Host "`nRebase stopped (conflict or error). Resolve, then:" -ForegroundColor Red
        Write-Host "  git rebase --continue" -ForegroundColor White
        Write-Host "  git rebase --abort        # to give up and return to the prior state" -ForegroundColor White
    }

    if ($stashed) {
        Write-Host "`nRestoring stashed changes..." -ForegroundColor Cyan
        & git stash pop
    }
}
finally {
    Pop-Location
}
