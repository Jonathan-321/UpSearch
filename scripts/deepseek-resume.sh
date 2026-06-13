#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKDOOR_DIR="${BACKDOOR_DIR:-$HOME/backdoor}"
SESSION_ID="${1:-}"
PROMPT="${2:-Continue the assigned task from the current state. Run the required verification, write the handoff, and stop.}"

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: scripts/deepseek-resume.sh <claude-session-id>" >&2
  exit 1
fi

if [[ ! -x "$BACKDOOR_DIR/run.sh" ]]; then
  echo "Backdoor launcher not found: $BACKDOOR_DIR/run.sh" >&2
  exit 1
fi

exec "$BACKDOOR_DIR/run.sh" "$ROOT" \
  --resume "$SESSION_ID" \
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
  --effort medium \
  --max-turns "${DEEPSEEK_MAX_TURNS:-20}" \
  --print \
  --output-format json \
  "$PROMPT"
