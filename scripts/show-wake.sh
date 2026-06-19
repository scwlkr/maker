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

if [ "$#" -ne 1 ]; then
  echo "usage: scripts/show-wake.sh WAKE_ID"
  exit 2
fi

MAKER_PLACE_DIR="${MAKER_PLACE_DIR:-maker-place}"
WAKE_ID="$1"
python3 - "$MAKER_PLACE_DIR/wakes/$WAKE_ID.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"wake not found: {path}")
data = json.loads(path.read_text())
print(f"wake: {data.get('wake_id')}")
print(f"model: {data.get('model')}")
print(f"start: {data.get('start_time')}")
print(f"end: {data.get('end_time')}")
print(f"reason: {data.get('end_reason')}")
print(f"tools: {len(data.get('tool_calls', []))}")
for call in data.get("tool_calls", [])[-10:]:
    print(f"- #{call.get('index')} {call.get('name')}: {call.get('arguments')}")
if data.get("errors"):
    print("errors:")
    for error in data["errors"]:
        print(f"- {error}")
PY
