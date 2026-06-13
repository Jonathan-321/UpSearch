#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKDOOR_DIR="${BACKDOOR_DIR:-$HOME/backdoor}"

if [[ ! -x "$BACKDOOR_DIR/run.sh" ]]; then
  echo "Backdoor launcher not found: $BACKDOOR_DIR/run.sh" >&2
  exit 1
fi

exec "$BACKDOOR_DIR/run.sh" "$ROOT" \
  --tools "Read,Edit,Write,Glob,Grep,Bash" \
  --permission-mode acceptEdits \
  --effort medium \
  --name "upsearch-deepseek"
