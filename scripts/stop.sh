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
PID_FILE="$MAKER_PLACE_DIR/controller.pid"
mkdir -p "$MAKER_PLACE_DIR"
touch "$MAKER_PLACE_DIR/stop"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      if ! kill -0 "$PID" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 "$PID" 2>/dev/null || true
    fi
  fi
  rm -f "$PID_FILE"
fi

if command -v docker >/dev/null 2>&1; then
  CONTAINERS="$(docker ps -aq --filter "label=maker.runtime=finn" 2>/dev/null || true)"
  if [ -n "$CONTAINERS" ]; then
    docker rm -f $CONTAINERS >/dev/null 2>&1 || true
  fi
fi

echo "controller stopped"
