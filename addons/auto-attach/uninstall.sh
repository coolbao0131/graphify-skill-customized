#!/bin/bash
# Remove the graphify auto-attach block (between BEGIN/END markers) from a CLAUDE.md.
#
# Usage:
#   ./uninstall.sh                            # ~/.claude/CLAUDE.md
#   TARGET=./CLAUDE.md ./uninstall.sh         # project-level

set -e

TARGET="${TARGET:-$HOME/.claude/CLAUDE.md}"

if [ ! -f "$TARGET" ]; then
    echo "  no $TARGET found — nothing to do."
    exit 0
fi

if ! grep -qF "BEGIN graphify-auto-attach" "$TARGET" 2>/dev/null; then
    echo "  graphify auto-attach block not found in $TARGET — already uninstalled."
    exit 0
fi

# Backup before modifying
cp "$TARGET" "$TARGET.bak.$(date +%Y%m%d-%H%M%S)"

# Rotate: keep only the most recent 5 backups
ls -t "${TARGET}".bak.* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true

# Use awk to drop everything between BEGIN and END markers (inclusive).
# Also strip the blank line right before BEGIN to avoid leaving stray gaps.
awk '
    /<!-- BEGIN graphify-auto-attach/ { drop = 1; next }
    /<!-- END graphify-auto-attach -->/ { drop = 0; next }
    drop { next }
    { print }
' "$TARGET" > "$TARGET.tmp"

# Trim trailing blank lines (collapsed multiple blanks at file end → single newline)
awk 'BEGIN{blank=0} /^$/{blank++; next} {while(blank-- > 0) print ""; blank=0; print}' \
    "$TARGET.tmp" > "$TARGET.tmp2"
mv "$TARGET.tmp2" "$TARGET"
rm -f "$TARGET.tmp"

echo "✓ removed graphify auto-attach from $TARGET"
echo "  backup: ${TARGET}.bak.<timestamp>"
