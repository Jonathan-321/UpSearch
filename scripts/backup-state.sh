#!/usr/bin/env bash
# ── UpSearch State Backup ─────────────────────────────────────────────────────
#
# Backs up:
#   - SQLite database
#   - .upsearch directory (tracking, profile cache, reports)
#   - profile.txt (if it exists)
#
# Refuses to overwrite an existing backup unless --force is passed.
#
# Usage:
#   bash scripts/backup-state.sh                    → creates timestamped backup
#   bash scripts/backup-state.sh --force            → overwrites latest backup
#   bash scripts/backup-state.sh /custom/path       → saves to custom path

set -euo pipefail

UPSEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$UPSEARCH_DIR"

BACKUP_DIR="${1:-$UPSEARCH_DIR/.upsearch/backups}"
FORCE="${FORCE:-false}"

if [ "${1:-}" == "--force" ]; then
    FORCE=true
    BACKUP_DIR="$UPSEARCH_DIR/.upsearch/backups"
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="upsearch-state-${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "$BACKUP_DIR"

# Check for overwrite
if [ -d "$BACKUP_PATH" ]; then
    if [ "$FORCE" != "true" ]; then
        echo "ERROR: Backup already exists: $BACKUP_PATH"
        echo "Use --force to overwrite."
        exit 1
    fi
    rm -rf "$BACKUP_PATH"
fi

mkdir -p "$BACKUP_PATH"

echo "=== UpSearch State Backup ==="
echo "  Source: $UPSEARCH_DIR"
echo "  Destination: $BACKUP_PATH"
echo ""

# Check what's available
HAS_DB=false
HAS_UPSEARCH=false
HAS_PROFILE=false
HAS_DOT_UPSEARCH=false

[ -f "opportunity_os.db" ] && HAS_DB=true
[ -d ".upsearch" ] && HAS_DOT_UPSEARCH=true
[ -f "profile.txt" ] && HAS_PROFILE=true

# Backup database
if [ "$HAS_DB" = true ]; then
    echo "  ✓ Backing up opportunity_os.db..."
    # Use VACUUM INTO for a consistent snapshot
    python3 -c "
import sqlite3
src = 'opportunity_os.db'
dst = '${BACKUP_PATH}/opportunity_os.db'
conn = sqlite3.connect(src)
conn.execute(f'VACUUM INTO \"{dst}\"')
conn.close()
" 2>/dev/null || cp "opportunity_os.db" "$BACKUP_PATH/opportunity_os.db"
else
    echo "  - No opportunity_os.db found"
fi

# Backup .upsearch directory
if [ "$HAS_DOT_UPSEARCH" = true ]; then
    echo "  ✓ Backing up .upsearch/..."
    # Exclude backups from backup
    rsync -a --exclude='backups/' --exclude='__pycache__/' \
        ".upsearch/" "$BACKUP_PATH/upsearch/"
else
    echo "  - No .upsearch/ directory found"
fi

# Backup profile
if [ "$HAS_PROFILE" = true ]; then
    echo "  ✓ Backing up profile.txt..."
    cp "profile.txt" "$BACKUP_PATH/profile.txt"
else
    echo "  - No profile.txt found"
fi

# Write manifest
cat > "$BACKUP_PATH/manifest.json" <<MANIFEST_EOF
{
  "backup_timestamp": "$TIMESTAMP",
  "backup_version": "1",
  "contents": {
    "database": $HAS_DB,
    "upsearch_dir": $HAS_DOT_UPSEARCH,
    "profile": $HAS_PROFILE
  },
  "source_dir": "$UPSEARCH_DIR"
}
MANIFEST_EOF

echo ""
echo "=== Backup complete: $BACKUP_PATH ==="
echo "  Size: $(du -sh "$BACKUP_PATH" 2>/dev/null | cut -f1 || echo '?')"
