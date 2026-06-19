#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_WORLD_VOLUME="${WORLD_VOLUME-}"
ENV_SANDBOX_IMAGE="${SANDBOX_IMAGE-}"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
if [ -n "$ENV_WORLD_VOLUME" ]; then
  WORLD_VOLUME="$ENV_WORLD_VOLUME"
fi
if [ -n "$ENV_SANDBOX_IMAGE" ]; then
  SANDBOX_IMAGE="$ENV_SANDBOX_IMAGE"
fi

WORLD_VOLUME="${WORLD_VOLUME:-maker_finn_world}"
SANDBOX_IMAGE="${SANDBOX_IMAGE:-maker-finn-sandbox:latest}"

docker volume create "$WORLD_VOLUME" >/dev/null
if ! docker image inspect "$SANDBOX_IMAGE" >/dev/null 2>&1; then
  docker build -f Dockerfile.sandbox -t "$SANDBOX_IMAGE" .
fi

docker run --rm -v "$WORLD_VOLUME:/world:ro" "$SANDBOX_IMAGE" bash -lc \
  'cd /world && if [ -z "$(find . -mindepth 1 -maxdepth 1 -print -quit)" ]; then echo "(empty)"; else find . -mindepth 1 -maxdepth "${MAX_DEPTH:-5}" -print | sort; fi'
