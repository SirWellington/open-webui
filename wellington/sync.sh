#!/usr/bin/env bash
#
# Wellington sync helper (bash)
#
# Purpose: rebase the `wellington` branch onto the latest upstream/main so the
# fork tracks open-webui/open-webui while keeping the Wellington customizations.
#
# Safety: NON-DESTRUCTIVE. Will not force-push, drop commits, or reset. Refuses
# a dirty working tree unless --force is passed (which only stashes/restores).
#
# Usage (from anywhere in the repo):
#   bash wellington/sync.sh              # status + fetch (no rebase)
#   bash wellington/sync.sh --rebase     # fetch + rebase onto upstream/main
#   bash wellington/sync.sh --rebase --force   # allow a dirty tree (auto stash/restore)
#
# Requires: git.

set -euo pipefail

REBASE=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --rebase) REBASE=1 ;;
    --force)  FORCE=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Resolve the repo root (this script lives in <root>/wellington/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]; then
  echo "Not inside a git repository at: $REPO_ROOT" >&2
  exit 1
fi

if ! git remote | grep -qx 'upstream'; then
  echo "Missing 'upstream' remote. Add it with:" >&2
  echo "  git remote add upstream https://github.com/open-webui/open-webui.git" >&2
  exit 1
fi

echo
echo "=== Wellington sync ==="
echo "Repo root : $REPO_ROOT"
echo "Branch    : $(git rev-parse --abbrev-ref HEAD)"

# --- Working tree check ---
DIRTY=$(git status --porcelain | grep -c . || true)
STASHED=0
if [ "$DIRTY" -gt 0 ]; then
  if [ "$FORCE" -ne 1 ]; then
    echo
    echo "Working tree has $DIRTY uncommitted change(s):"
    git status --short
    echo
    echo "Commit or stash them first, then re-run with --rebase."
    echo "Or re-run with --force to let this script stash/restore them."
    exit 1
  else
    echo
    echo "Stashing $DIRTY uncommitted change(s) (will restore after)..."
    git stash push -u -m "wellington-sync-autostash"
    STASHED=1
  fi
fi

counts=$(git fetch --all --prune >/dev/null 2>&1; git rev-list --left-right --count upstream/main...HEAD)
BEHIND="${counts%% *}"
AHEAD="${counts##* }"

if [ "$REBASE" -ne 1 ]; then
  echo
  echo "Behind upstream/main : $BEHIND"
  echo "Ahead  of upstream/main: $AHEAD"
  if [ "$BEHIND" -eq 0 ]; then
    echo
    echo "Already up to date with upstream/main. Nothing to rebase."
  else
    echo
    echo "$BEHIND new upstream commit(s). Re-run with --rebase to rebase."
  fi
  [ "$STASHED" -eq 1 ] && git stash pop
  exit 0
fi

if [ "$BEHIND" -eq 0 ]; then
  echo
  echo "Already up to date with upstream/main. Nothing to rebase."
  [ "$STASHED" -eq 1 ] && git stash pop
  exit 0
fi

# Known conflict-surface files (modified relative to upstream).
CONFLICT_SURFACE=(
  "Dockerfile"
  "backend/open_webui/models/automations.py"
  "backend/open_webui/routers/tasks.py"
  "backend/open_webui/utils/automations.py"
  "backend/open_webui/utils/middleware.py"
  "src/lib/apis/automations/index.ts"
  "src/lib/components/AutomationModal.svelte"
  "src/lib/components/automations/AutomationEditor.svelte"
  "src/lib/components/automations/ChatTargetDropdown.svelte"
  "src/lib/components/common/Select.svelte"
  "src/lib/components/layout/Sidebar/ChatItem.svelte"
  "src/lib/i18n/locales/en-US/translation.json"
)

echo
echo "Rebasing onto upstream/main ($BEHIND upstream commit(s))..."
echo "Files you have modified that MAY conflict:"
for f in "${CONFLICT_SURFACE[@]}"; do echo "  - $f"; done
echo

set +e
git rebase upstream/main
rc=$?
set -e

if [ "$rc" -eq 0 ]; then
  echo
  echo "Rebase succeeded."
else
  echo
  echo "Rebase stopped (conflict or error). Resolve, then:"
  echo "  git rebase --continue"
  echo "  git rebase --abort        # to give up and return to the prior state"
fi

[ "$STASHED" -eq 1 ] && { echo; echo "Restoring stashed changes..."; git stash pop; }
