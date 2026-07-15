#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

./scripts/rgw-analysis-web/validate-features.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cp features.yaml "$tmp/renderer.yaml"
sed -i 's/renderer: helm\/v1/renderer: unknown\/v1/' "$tmp/renderer.yaml"
if ./scripts/rgw-analysis-web/validate-features.sh "$tmp/renderer.yaml" . >/dev/null 2>&1; then
  echo "unknown renderer unexpectedly passed" >&2
  exit 1
fi

cp features.yaml "$tmp/path.yaml"
sed -i 's#chart: charts/rgw-analysis-web#chart: charts/missing#' "$tmp/path.yaml"
if ./scripts/rgw-analysis-web/validate-features.sh "$tmp/path.yaml" . >/dev/null 2>&1; then
  echo "missing registry path unexpectedly passed" >&2
  exit 1
fi

echo "negative feature registry: PASS"
