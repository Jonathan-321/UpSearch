#!/usr/bin/env bash
set -euo pipefail

# ── Golden Packet Acceptance Runner ──────────────────────────────────────────
#
# Runs the full golden acceptance test suite. No network or credentials are
# required — all fixtures are self-contained.
#
# Usage:
#   bash scripts/run-golden-acceptance.sh          # full suite
#   bash scripts/run-golden-acceptance.sh --report  # also print the acceptance report

UPSEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$UPSEARCH_DIR"

echo "=== Golden Packet Acceptance ==="
echo ""

# Run the pytest-based tests
echo "--- pytest: test_golden_packets.py ---"
uv run pytest -q tests/test_golden_packets.py
echo ""

# Also run the harness programmatically to produce the human-readable report
echo "--- Acceptance harness report ---"
uv run python -c "
from upsearch.acceptance import run_golden_acceptance, report
results = run_golden_acceptance()
print(report(results))
"

# If --report flag was passed, also show per-criterion detail
if [[ "${1:-}" == "--report" ]]; then
  echo ""
  echo "--- Per-criterion detail ---"
  uv run python -c "
from upsearch.acceptance import run_golden_acceptance
results = run_golden_acceptance()
for company, r in results.items():
    print(f'\\n## {company}')
    print(f'  all_passed: {r.all_passed}')
    print(f'  checkup score: {r.checkup[\"overall_score\"]}/10')
    print(f'  checkup status: {r.checkup[\"status\"]}')
    for c in r.criteria:
        icon = 'PASS' if c.passed else 'FAIL'
        print(f'    [{icon}] {c.name} — {c.detail}')
"
fi

echo ""
echo "=== Done ==="
