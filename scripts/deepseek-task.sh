#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKDOOR_DIR="${BACKDOOR_DIR:-$HOME/backdoor}"
TASK="${1:-agent/tasks/001-people-source-connectors.md}"
MAX_TURNS="${DEEPSEEK_MAX_TURNS:-6}"

if [[ ! -f "$ROOT/$TASK" ]]; then
  echo "Task file not found: $ROOT/$TASK" >&2
  exit 1
fi

if [[ ! -x "$BACKDOOR_DIR/run.sh" ]]; then
  echo "Backdoor launcher not found: $BACKDOOR_DIR/run.sh" >&2
  exit 1
fi

mkdir -p "$ROOT/.upsearch/agent-runs"
TASK_ID="$(basename "$TASK" .md)"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RAW_LOG="$ROOT/.upsearch/agent-runs/$TASK_ID-$RUN_STAMP.log"
RESULT_JSON="$ROOT/.upsearch/agent-runs/$TASK_ID-$RUN_STAMP-result.json"

PROMPT="Execute exactly one task: $TASK
Read CLAUDE.md first and follow its read limits, write scope, verification, and handoff contract.
Do not read unrelated files. Run only the verification commands named by the task.
Once those commands pass, write the handoff and stop.
Do not start another task. Do not commit or push."

set +e
"$BACKDOOR_DIR/run.sh" "$ROOT" \
  --bare \
  --append-system-prompt-file "$ROOT/CLAUDE.md" \
  --tools "Read,Edit,Write,Glob,Grep,Bash" \
  --permission-mode bypassPermissions \
  --disallowedTools \
    "Read(.env)" \
    "Read(**/.env)" \
    "Bash(git push *)" \
    "Bash(git commit *)" \
    "Bash(git reset *)" \
    "Bash(git clean *)" \
    "Bash(rm -rf *)" \
    "Bash(gh *)" \
    "Bash(ssh *)" \
  --effort low \
  --max-turns "$MAX_TURNS" \
  --name "upsearch-$(basename "$TASK" .md)" \
  --print \
  --output-format json \
  "$PROMPT" | tee "$RAW_LOG"
RUN_STATUS="${PIPESTATUS[0]}"
set -e

echo ""
python3 - "$RAW_LOG" "$RESULT_JSON" <<'PY'
import json
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
lines = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()

for line in reversed(lines):
    candidate = line.strip()
    if not candidate.startswith("{"):
        continue
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        continue
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    break
else:
    result_path.write_text(
        json.dumps(
            {
                "subtype": "launcher_error",
                "is_error": True,
                "result": "No machine-readable Claude Code result was found.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
PY

echo "Captured raw log → $RAW_LOG"
echo "Captured result  → $RESULT_JSON"
SESSION_ID="$(
  python3 - "$RESULT_JSON" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("")
else:
    print(payload.get("session_id", ""))
PY
)"
if [[ -n "$SESSION_ID" ]]; then
  echo "Claude session   → $SESSION_ID"
  echo "Resume with      → scripts/deepseek-resume.sh $SESSION_ID"
fi
exit "$RUN_STATUS"
