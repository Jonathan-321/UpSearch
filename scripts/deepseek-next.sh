#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/agent/task-queue.yaml"

TASK="$(
  awk '
    /^[[:space:]]+file:/ {
      file = $2
    }
    /^[[:space:]]+status:[[:space:]]+ready/ {
      print file
      exit
    }
  ' "$QUEUE"
)"

if [[ -z "$TASK" ]]; then
  echo "No ready DeepSeek task in agent/task-queue.yaml"
  exit 0
fi

echo "Delegating → $TASK"
if [[ "${1:-}" == "--dry-run" ]]; then
  exit 0
fi

exec "$ROOT/scripts/deepseek-task.sh" "$TASK"
