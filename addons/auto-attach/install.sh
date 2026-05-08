#!/bin/bash
# Patch a CLAUDE.md to auto-attach the graphify graph as persistent memory.
#
# By default, modifies ~/.claude/CLAUDE.md (your global personal instructions).
# Override with TARGET=<path> to install into a project-level CLAUDE.md instead.
#
# Idempotent: if the section is already present (between BEGIN/END markers),
# the script is a no-op. Run uninstall.sh first if you want to refresh.
#
# Usage:
#   ./install.sh                            # patch ~/.claude/CLAUDE.md
#   TARGET=./CLAUDE.md ./install.sh         # patch project-level CLAUDE.md
#   ./install.sh --dry-run                  # show what would be added, don't write

set -e
cd "$(dirname "$0")"

TARGET="${TARGET:-$HOME/.claude/CLAUDE.md}"
SECTION_FILE="$(pwd)/auto-attach-section.md"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

BEGIN_MARK="<!-- BEGIN graphify-auto-attach (managed by graphify-skill-customized; remove block to disable) -->"
END_MARK="<!-- END graphify-auto-attach -->"

if [ ! -f "$SECTION_FILE" ]; then
    echo "ERROR: $SECTION_FILE not found. Run from the addons/auto-attach/ dir." >&2
    exit 1
fi

if [ ! -f "$TARGET" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "(dry-run) Would create $TARGET"
    else
        mkdir -p "$(dirname "$TARGET")"
        touch "$TARGET"
        echo "✓ created $TARGET (was empty)"
    fi
fi

if [ -f "$TARGET" ] && grep -qF "BEGIN graphify-auto-attach" "$TARGET" 2>/dev/null; then
    echo "  already installed in $TARGET — no change."
    echo "  (run ./uninstall.sh first if you want to update with the latest section text)"
    exit 0
fi

CONTENT="$(cat "$SECTION_FILE")"
BLOCK=$(printf '\n%s\n%s\n%s\n' "$BEGIN_MARK" "$CONTENT" "$END_MARK")

if [ "$DRY_RUN" -eq 1 ]; then
    echo "(dry-run) Would APPEND the following to $TARGET:"
    echo "================================================================"
    echo "$BLOCK"
    echo "================================================================"
    echo "Run again without --dry-run to actually install."
    exit 0
fi

# Backup target before modifying
cp "$TARGET" "$TARGET.bak.$(date +%Y%m%d-%H%M%S)"

# Rotate: keep only the most recent 5 backups (avoid disk pollution).
# `ls -t` newest-first, `tail -n +6` skips the first 5.
ls -t "${TARGET}".bak.* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true

printf '%s' "$BLOCK" >> "$TARGET"

LINES_ADDED=$(printf '%s' "$BLOCK" | wc -l | tr -d ' ')
TOKEN_ESTIMATE=$(( $(wc -c < "$SECTION_FILE") / 4 ))
echo "✓ installed graphify auto-attach into $TARGET"
echo "  +$LINES_ADDED lines, ~$TOKEN_ESTIMATE tokens loaded per session"
echo "  backup: ${TARGET}.bak.<timestamp>"
echo ""
echo "Test:    Open a new Claude Code session in any directory that has graphify-out/."
echo "         Claude should auto-read GRAPH_REPORT.md before answering."
echo "Disable: ./uninstall.sh   (or say 'skip graphify' mid-session)"
