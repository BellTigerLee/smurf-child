#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

export SOURCE_DATE_EPOCH=0
export SOURCE_REVISION=0123456789abcdef0123456789abcdef01234567
export SOURCE_TREE=89abcdef0123456789abcdef0123456789abcdef
export FLOW_SOURCE_REVISION=1111111111111111111111111111111111111111
export WEB_SOURCE_REVISION=2222222222222222222222222222222222222222
export FLOW_IMAGE_TAG="sha-$FLOW_SOURCE_REVISION"
FLOW_IMAGE_DIGEST="sha256:$(printf '1%.0s' {1..64})"
export FLOW_IMAGE_DIGEST
export WEB_IMAGE_TAG="sha-$WEB_SOURCE_REVISION"
WEB_IMAGE_DIGEST="sha256:$(printf '2%.0s' {1..64})"
export WEB_IMAGE_DIGEST
export CI_RUN_URL=https://github.com/BellTigerLee/smurf-child/actions/runs/1

rm -rf dist/rgw-analysis-web
./scripts/package-chart.sh
first="$(sha256sum dist/rgw-analysis-web/rgw-analysis-web-0.1.0.tgz)"
./scripts/package-chart.sh
second="$(sha256sum dist/rgw-analysis-web/rgw-analysis-web-0.1.0.tgz)"
test "$first" = "$second"

metadata=dist/rgw-analysis-web/promotion.yaml
grep -Fxq 'apiVersion: scalex.io/promotion/v1' "$metadata"
grep -Fxq "  revision: $SOURCE_REVISION" "$metadata"
grep -Fxq '    repository: ghcr.io/belltigerlee/smurf-child-flow' "$metadata"
grep -Fxq '    repository: ghcr.io/belltigerlee/smurf-child-web' "$metadata"
grep -Fxq "    sourceRevision: $FLOW_SOURCE_REVISION" "$metadata"
grep -Fxq "    sourceRevision: $WEB_SOURCE_REVISION" "$metadata"
grep -Fxq "    tag: $FLOW_IMAGE_TAG" "$metadata"
grep -Fxq "    digest: $WEB_IMAGE_DIGEST" "$metadata"
tar -tzf dist/rgw-analysis-web/rgw-analysis-web-0.1.0.tgz | sort -c
helm_bin=${HELM_BIN:-helm}
if command -v "$helm_bin" >/dev/null 2>&1; then
  "$helm_bin" lint dist/rgw-analysis-web/rgw-analysis-web-0.1.0.tgz \
    --strict \
    --values tests/rgw-analysis-web/fixtures/values.valid.yaml
fi

if FLOW_IMAGE_TAG=latest ./scripts/package-chart.sh >/dev/null 2>&1; then
  echo "mutable promotion tag unexpectedly passed" >&2
  exit 1
fi

echo "deterministic package: PASS"
