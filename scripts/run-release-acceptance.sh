#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/upsearch-release.XXXXXX")"
REPORT="$STATE_DIR/release-report.txt"
trap 'rm -rf "$STATE_DIR"' EXIT

export UPSEARCH_DIR="$STATE_DIR/.upsearch"
export UPSEARCH_DB_PATH="$STATE_DIR/opportunity_os.db"
export UPSEARCH_TRACKING_DIR="$STATE_DIR/.upsearch/runs"

cd "$ROOT"

echo "=== UpSearch Phase 1 Release Acceptance ==="
echo "State: $STATE_DIR"

# Every step below is executed and its measured PASS/FAIL recorded; the final
# report prints only measured results, never constants. All steps run even
# after a failure so the report is complete, and any failure exits nonzero.
STEP_NAMES=()
STEP_RESULTS=()
FAILED_STEPS=0

run_step() {
  local name="$1"
  shift
  echo
  echo "--- $name ---"
  local result="PASS"
  if ! "$@"; then
    result="FAIL"
    FAILED_STEPS=$((FAILED_STEPS + 1))
  fi
  STEP_NAMES+=("$name")
  STEP_RESULTS+=("$result")
  echo "[$result] $name"
}

step_clean_state() {
  uv run python - <<'PY'
import os
from pathlib import Path

import db

expected = Path(os.environ["UPSEARCH_DB_PATH"])
if Path(db.DB_PATH) != expected:
    raise SystemExit(
        f"db.DB_PATH={db.DB_PATH} ignores UPSEARCH_DB_PATH={expected}; "
        "this step would run against the real repository database"
    )
db.init_db()
if not expected.exists():
    raise SystemExit(f"init_db() did not create {expected}")
print(f"ready: temporary database created at {expected}")
PY
}

step_migration_readiness() {
  uv run python - <<'PY'
import db
from upsearch.runtime import check_migration_state

db.init_db()
state = check_migration_state(db.DB_PATH)
if state.pending_migrations:
    raise SystemExit("Pending migrations: " + "; ".join(state.pending_migrations))
print(f"ready: {len(state.tables_found)} tables, no pending migrations")
PY
}

run_step "clean temporary state initialization" step_clean_state
run_step "migration readiness" step_migration_readiness
run_step "Baseten and Modal golden packet acceptance" bash scripts/run-golden-acceptance.sh
run_step "restart and action-safety integration (run lineage, approval gate, delivery and follow-up, restart idempotency)" \
  uv run pytest -q tests/test_release_integration.py

{
  echo "UpSearch Phase 1 release report"
  echo
  for i in "${!STEP_NAMES[@]}"; do
    echo "${STEP_RESULTS[$i]} ${STEP_NAMES[$i]}"
  done
  echo
  echo "Manual checks remaining:"
  echo "- Run one real-model packet with configured provider credentials."
  echo "- Review one authenticated Gmail and LinkedIn handoff without automatic send."
  echo "- Confirm production volume backup and restore on the target host."
} >"$REPORT"

echo
cat "$REPORT"
echo
if [ "$FAILED_STEPS" -gt 0 ]; then
  echo "=== Release acceptance FAILED: $FAILED_STEPS of ${#STEP_NAMES[@]} steps failed ==="
  exit 1
fi
echo "=== Release acceptance passed: ${#STEP_NAMES[@]} of ${#STEP_NAMES[@]} steps measured PASS ==="
