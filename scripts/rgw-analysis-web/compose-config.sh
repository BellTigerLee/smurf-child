#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
: "${MINIO_IMAGE:?set an immutable MINIO_IMAGE}"
: "${MINIO_MC_IMAGE:?set an immutable MINIO_MC_IMAGE}"
: "${MINIO_ROOT_USER:?set MINIO_ROOT_USER}"
: "${MINIO_ROOT_PASSWORD:?set MINIO_ROOT_PASSWORD}"
docker compose -f images/docker-compose.yaml config --quiet
