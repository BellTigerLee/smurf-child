#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
revision=${SOURCE_REVISION:?set the full source revision}
[[ $revision =~ ^[0-9a-f]{40}$ ]] || { echo "SOURCE_REVISION must be a full commit" >&2; exit 1; }

docker buildx build \
  --file images/rgw-analysis-web/flow/Containerfile \
  --build-context flow-source=src/rgw-analysis-web/flow \
  --build-context web-source=src/rgw-analysis-web/web \
  --build-context project-source=. \
  --tag "smurf-child-flow:sha-$revision" \
  images/rgw-analysis-web/flow
docker buildx build \
  --file images/rgw-analysis-web/web/Containerfile \
  --build-context web-source=src/rgw-analysis-web/web \
  --tag "smurf-child-web:sha-$revision" \
  images/rgw-analysis-web/web
