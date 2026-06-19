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
EVENTS="$MAKER_PLACE_DIR/events.jsonl"
mkdir -p "$MAKER_PLACE_DIR"
touch "$EVENTS"
tail -n "${LINES:-50}" -f "$EVENTS"
