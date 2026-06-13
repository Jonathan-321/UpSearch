#!/usr/bin/env bash
# ── UpSearch State Restore ────────────────────────────────────────────────────
#
# Restores a backup created by backup-state.sh.
#
# Safety: refuses to restore if the target database already has data
# (companies table non-empty) unless --force is passed.
#
# Usage:
#   bash scripts/restore-state.sh                    → restores latest backup
#   bash scripts/restore-state.sh --force            → overwrite existing state
#   bash scripts/restore-state.sh /path/to/backup    → specific backup

set -euo pipefail

UPSEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$UPSEARCH_DIR"

FORCE=false
RESTORE_SRC=""

# Parse arguments
for arg in "$@"; do
    if [ "$arg" == "--force" ]; then
        FORCE=true
    elif [ -d "$arg" ]; then
        RESTORE_SRC="$arg"
    fi
done

# If no path given, find the latest backup
if [ -z "$RESTORE_SRC" ]; then
    BACKUP_DIR="$UPSEARCH_DIR/.upsearch/backups"
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "ERROR: No backup directory found at $BACKUP_DIR"
        echo "Specify a backup path: bash scripts/restore-state.sh /path/to/backup"
        exit 1
    fi
    RESTORE_SRC=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "upsearch-state-*" | sort | tail -1)
    if [ -z "$RESTORE_SRC" ]; then
        echo "ERROR: No backups found in $BACKUP_DIR"
        exit 1
    fi
fi

if [ ! -f "$RESTORE_SRC/manifest.json" ]; then
    echo "ERROR: '$RESTORE_SRC' does not contain a manifest.json"
    echo "Is this a valid UpSearch backup?"
    exit 1
fi

echo "=== UpSearch State Restore ==="
echo "  Source: $RESTORE_SRC"
echo "  Target: $UPSEARCH_DIR"
echo ""

# Safety check: refuse to overwrite non-empty database without --force
if [ -f "opportunity_os.db" ] && [ "$FORCE" != "true" ]; then
    COMPANY_COUNT=$(python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('opportunity_os.db')
    count = conn.execute('SELECT COUNT(*) FROM companies').fetchone()[0]
    conn.close()
    print(count)
except Exception:
    print('-1')
" 2>/dev/null || echo "0")
    if [ "$COMPANY_COUNT" -gt 0 ]; then
        echo "ERROR: Target database has $COMPANY_COUNT companies."
        echo "Use --force to overwrite."
        exit 1
    fi
fi

# Check backup contents
BACKUP_DB="$RESTORE_SRC/opportunity_os.db"
BACKUP_UPSEARCH="$RESTORE_SRC/upsearch"
BACKUP_PROFILE="$RESTORE_SRC/profile.txt"

restored_count=0

# Restore database
if [ -f "$BACKUP_DB" ]; then
    echo "  ✓ Restoring opportunity_os.db..."
    cp "$BACKUP_DB" "opportunity_os.db"
    restored_count=$((restored_count + 1))
else
    echo "  - No database in backup"
fi

# Restore .upsearch directory
if [ -d "$BACKUP_UPSEARCH" ]; then
    echo "  ✓ Restoring .upsearch/..."
    mkdir -p ".upsearch"
    rsync -a "$BACKUP_UPSEARCH/" ".upsearch/"
    restored_count=$((restored_count + 1))
else
    echo "  - No .upsearch/ in backup"
fi

# Restore profile
if [ -f "$BACKUP_PROFILE" ]; then
    echo "  ✓ Restoring profile.txt..."
    cp "$BACKUP_PROFILE" "profile.txt"
    restored_count=$((restored_count + 1))
else
    echo "  - No profile.txt in backup"
fi

echo ""
if [ "$restored_count" -gt 0 ]; then
    echo "=== Restore complete: $restored_count items restored from $RESTORE_SRC ==="
else
    echo "=== Nothing to restore ==="
fi
