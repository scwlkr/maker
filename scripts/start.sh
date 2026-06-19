#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_MAKER_PLACE_DIR="${MAKER_PLACE_DIR-}"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
if [ -n "$ENV_MAKER_PLACE_DIR" ]; then
  MAKER_PLACE_DIR="$ENV_MAKER_PLACE_DIR"
fi

MAKER_PLACE_DIR="${MAKER_PLACE_DIR:-maker-place}"
mkdir -p "$MAKER_PLACE_DIR"
PID_FILE="$MAKER_PLACE_DIR/controller.pid"
LOG_FILE="$MAKER_PLACE_DIR/controller.log"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "controller already running: $(cat "$PID_FILE")"
  exit 0
fi

rm -f "$MAKER_PLACE_DIR/stop"
nohup python3 controller.py loop >> "$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"
echo "controller started: $(cat "$PID_FILE")"
echo "log: $LOG_FILE"
