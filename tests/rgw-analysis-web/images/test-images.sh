#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

for component in flow web; do
  file="images/rgw-analysis-web/$component/Containerfile"
  grep -Fq 'COPY --from=' "$file"
  if rg -n -i '(kubectl|karmada|kubeconfig|cluster-admin)' "images/rgw-analysis-web/$component"; then
    echo "$component image context contains cluster behavior" >&2
    exit 1
  fi
done

grep -Fq 'additional_contexts:' images/docker-compose.yaml
grep -Fq 'flow-source:' images/docker-compose.yaml
grep -Fq 'web-source:' images/docker-compose.yaml
grep -Fq 'current:/srv/viewer' images/docker-compose.yaml

build_compose=images/docker-compose.build.yaml
grep -Fq 'image: ${FLOW_IMAGE_REPOSITORY:-belltigerlee/test-image-flow}:${FLOW_IMAGE_TAG:-0.1.0}' "$build_compose"
grep -Fq 'image: ${WEB_IMAGE_REPOSITORY:-belltigerlee/test-image-web}:${WEB_IMAGE_TAG:-0.1.0}' "$build_compose"
grep -Fq 'flow-source: ../src/rgw-analysis-web/flow' "$build_compose"
grep -Fq 'web-source: ../src/rgw-analysis-web/web' "$build_compose"
grep -Fq 'project-source: ..' "$build_compose"
grep -Fq 'x-publication-scope: manual-development-only' "$build_compose"
grep -Fq '`0.1.0` image는 수동 개발·검증용이다.' README.md
grep -Fq 'docker logout' README.md

./scripts/rgw-analysis-web/validate-image-contexts.sh
if rg -n 'pip[[:space:]]+install' images/rgw-analysis-web/flow/Containerfile; then
  echo "flow image dependency install bypasses uv.lock" >&2
  exit 1
fi
grep -Eq '^FROM ghcr\.io/astral-sh/uv:[0-9]+\.[0-9]+\.[0-9]+@sha256:[0-9a-f]{64} AS uv$' images/rgw-analysis-web/flow/Containerfile
grep -Fq 'uv sync --frozen --no-dev --no-editable' images/rgw-analysis-web/flow/Containerfile
grep -Fq 'COPY --from=builder /opt/venv /opt/venv' images/rgw-analysis-web/flow/Containerfile
grep -Fq 'COPY --from=web-source fixtures/loading.html /srv/viewer/current/index.html' images/rgw-analysis-web/web/Containerfile
runtime_dependencies="$(sed -n '/^dependencies = \[/,/^\]/p' pyproject.toml)"
if grep -Fq 'types-boto3' <<<"$runtime_dependencies"; then
  echo "typing-only dependency would be installed in the runtime image" >&2
  exit 1
fi
grep -Fq '"types-boto3[s3]' pyproject.toml

if command -v docker >/dev/null 2>&1; then
  docker compose -f images/docker-compose.build.yaml config --quiet
  default_images="$(env \
    -u FLOW_IMAGE_REPOSITORY \
    -u FLOW_IMAGE_TAG \
    -u WEB_IMAGE_REPOSITORY \
    -u WEB_IMAGE_TAG \
    docker compose --env-file /dev/null -f images/docker-compose.build.yaml config --images | sort)"
  test "$default_images" = $'belltigerlee/test-image-flow:0.1.0\nbelltigerlee/test-image-web:0.1.0'

  override_images="$(
    FLOW_IMAGE_REPOSITORY=example/flow \
    FLOW_IMAGE_TAG=9.8.7 \
    WEB_IMAGE_REPOSITORY=example/web \
    WEB_IMAGE_TAG=6.5.4 \
      docker compose --env-file /dev/null -f images/docker-compose.build.yaml config --images | sort
  )"
  test "$override_images" = $'example/flow:9.8.7\nexample/web:6.5.4'

  MINIO_IMAGE='minio/minio:fixture@sha256:1111111111111111111111111111111111111111111111111111111111111111' \
  MINIO_MC_IMAGE='minio/mc:fixture@sha256:2222222222222222222222222222222222222222222222222222222222222222' \
  MINIO_ROOT_USER=fixture-user \
  MINIO_ROOT_PASSWORD=fixture-password \
    docker compose -f images/docker-compose.yaml config --quiet
fi

echo "image contracts: PASS"
