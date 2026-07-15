#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

uv lock --check
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen basedpyright
./scripts/test.sh

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
revision="$(git rev-parse HEAD)"
[[ $revision =~ ^[0-9a-f]{40}$ ]] || { echo "HEAD must be a full commit" >&2; exit 1; }

FLOW_IMAGE_REPOSITORY=smurf-child-flow \
FLOW_IMAGE_TAG="sha-$revision" \
WEB_IMAGE_REPOSITORY=smurf-child-web \
WEB_IMAGE_TAG="sha-$revision" \
  docker compose --env-file /dev/null -f images/docker-compose.build.yaml build

docker image inspect \
  "smurf-child-flow:sha-$revision" \
  "smurf-child-web:sha-$revision"
