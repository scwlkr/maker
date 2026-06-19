#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_MAKER_PLACE_DIR="${MAKER_PLACE_DIR-}"
ENV_WORLD_VOLUME="${WORLD_VOLUME-}"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
if [ -n "$ENV_MAKER_PLACE_DIR" ]; then
  MAKER_PLACE_DIR="$ENV_MAKER_PLACE_DIR"
fi
if [ -n "$ENV_WORLD_VOLUME" ]; then
  WORLD_VOLUME="$ENV_WORLD_VOLUME"
fi

MAKER_PLACE_DIR="${MAKER_PLACE_DIR:-maker-place}"
PID_FILE="$MAKER_PLACE_DIR/controller.pid"
WORLD_VOLUME="${WORLD_VOLUME:-maker_finn_world}"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "controller is running; stop it before resetting world"
  exit 1
fi

docker volume rm "$WORLD_VOLUME" >/dev/null 2>&1 || true
docker volume create "$WORLD_VOLUME" >/dev/null
echo "reset world volume: $WORLD_VOLUME"
