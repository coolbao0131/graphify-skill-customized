#!/bin/bash
# Install macOS launchd weekly job to refresh the NotebookLM meta-graph.
#
# Default: every Sunday 03:00 local time (laptop sleep-aware via launchd).
# Override with env vars:
#   WEEKDAY=0 HOUR=3 MINUTE=0   (0=Sun..6=Sat)
#   LABEL=com.example.foo
#
# Usage:
#   ./install.sh
#   WEEKDAY=3 HOUR=2 ./install.sh   # Wednesday 02:00 instead

set -e
cd "$(dirname "$0")"

WEEKDAY="${WEEKDAY:-0}"        # Sunday
HOUR="${HOUR:-3}"
MINUTE="${MINUTE:-0}"
USERNAME="$(id -un)"
LABEL="${LABEL:-com.${USERNAME}.graphify-notebooks-sync}"

NOTEBOOKS_DIR="$(cd .. && pwd)"
RUNNER_PATH="$NOTEBOOKS_DIR/.weekly-sync.sh"
LOG_DIR="$HOME/Library/Logs"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/$LABEL.plist"

# Detect notebooklm-mcp-cli Python (where notebooklm_tools is installed)
detect_python() {
    if command -v nlm >/dev/null 2>&1; then
        local nlm_bin="$(command -v nlm)"
        local nlm_dir="$(dirname "$nlm_bin")"
        local candidate="$nlm_dir/python"
        [ -x "$candidate" ] && { echo "$candidate"; return; }
        candidate="$nlm_dir/python3"
        [ -x "$candidate" ] && { echo "$candidate"; return; }
    fi
    # uv tool default location
    local uv_default="$HOME/.local/share/uv/tools/notebooklm-mcp-cli/bin/python"
    [ -x "$uv_default" ] && { echo "$uv_default"; return; }
    echo "ERROR: cannot find notebooklm_tools Python (install with: uv tool install notebooklm-mcp-cli)" >&2
    exit 1
}
PYTHON="$(detect_python)"

# Verify it can import notebooklm_tools
if ! "$PYTHON" -c "import notebooklm_tools" 2>/dev/null; then
    echo "ERROR: $PYTHON cannot import notebooklm_tools — install nlm CLI first:" >&2
    echo "  uv tool install notebooklm-mcp-cli" >&2
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS" "$LOG_DIR"

# Generate runner script
cat > "$RUNNER_PATH" << EOF
#!/bin/bash
set -e
cd "$NOTEBOOKS_DIR"
{
  echo ""
  echo "===== \$(date '+%Y-%m-%d %H:%M:%S %Z') sync start ====="
  "$PYTHON" cli.py sync --update --refresh-summaries 2>&1
  echo "===== \$(date '+%Y-%m-%d %H:%M:%S %Z') sync end ====="
} >> "$LOG_DIR/graphify-notebooks-sync.log"
EOF
chmod +x "$RUNNER_PATH"

# Render plist from template
sed \
    -e "s|{{LABEL}}|$LABEL|g" \
    -e "s|{{RUNNER_PATH}}|$RUNNER_PATH|g" \
    -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
    -e "s|{{WEEKDAY}}|$WEEKDAY|g" \
    -e "s|{{HOUR}}|$HOUR|g" \
    -e "s|{{MINUTE}}|$MINUTE|g" \
    com.user.graphify-notebooks-sync.plist.template > "$PLIST"

# Bootstrap into user's launchd domain (modern way; replaces deprecated `load`)
launchctl bootout "gui/$UID" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/$LABEL"

WD_NAME=("Sun" "Mon" "Tue" "Wed" "Thu" "Fri" "Sat")
echo "✓ installed:"
echo "  Label:   $LABEL"
echo "  Plist:   $PLIST"
echo "  Runner:  $RUNNER_PATH"
echo "  Trigger: every ${WD_NAME[$WEEKDAY]} at $(printf '%02d:%02d' $HOUR $MINUTE) local"
echo "  Logs:    $LOG_DIR/graphify-notebooks-sync.log"
echo ""
echo "Test now:    launchctl kickstart gui/$UID/$LABEL"
echo "Status:      launchctl print gui/$UID/$LABEL | head -30"
echo "Uninstall:   ./uninstall.sh"
