#!/bin/bash
# Remove the launchd weekly job + runner + plist.
# Logs are preserved.

set -e
cd "$(dirname "$0")"

USERNAME="$(id -un)"
LABEL="${LABEL:-com.${USERNAME}.graphify-notebooks-sync}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
NOTEBOOKS_DIR="$(cd .. && pwd)"
RUNNER_PATH="$NOTEBOOKS_DIR/.weekly-sync.sh"

if [ -f "$PLIST" ]; then
    launchctl bootout "gui/$UID" "$PLIST" 2>/dev/null || true
    rm "$PLIST"
    echo "✓ removed $PLIST"
else
    echo "  (no plist at $PLIST — already uninstalled)"
fi

if [ -f "$RUNNER_PATH" ]; then
    rm "$RUNNER_PATH"
    echo "✓ removed runner $RUNNER_PATH"
fi

echo ""
echo "Logs preserved at: ~/Library/Logs/graphify-notebooks-sync*.log"
echo "Remove logs:       rm ~/Library/Logs/graphify-notebooks-sync*.log"
