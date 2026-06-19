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
LAST="$(find "$MAKER_PLACE_DIR/wakes" -name '*.json' -type f 2>/dev/null | sort | tail -n 1 || true)"
if [ -z "$LAST" ]; then
  echo "no wakes found"
  exit 1
fi

scripts/show-wake.sh "$(basename "$LAST" .json)"
