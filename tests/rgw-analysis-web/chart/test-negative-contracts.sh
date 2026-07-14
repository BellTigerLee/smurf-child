#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

base_values=tests/rgw-analysis-web/fixtures/values.valid.yaml
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

expect_failure() {
  local name=$1
  shift
  if "$@" >"$tmp/$name.out" 2>&1; then
    echo "negative case unexpectedly passed: $name" >&2
    exit 1
  fi
}

cp "$base_values" "$tmp/latest.yaml"
sed -i '0,/tag: sha-[0-9a-f]*/s//tag: latest/' "$tmp/latest.yaml"
expect_failure latest ./scripts/validate-chart.sh "$tmp/latest.yaml"

cp "$base_values" "$tmp/missing-digest.yaml"
sed -i '0,/digest: sha256:/s//digest: /' "$tmp/missing-digest.yaml"
expect_failure missing-digest ./scripts/validate-chart.sh "$tmp/missing-digest.yaml"

cp "$base_values" "$tmp/empty-annotations.yaml"
sed -i '/    scalex.io\/contract:/d' "$tmp/empty-annotations.yaml"
expect_failure empty-annotations ./scripts/validate-chart.sh "$tmp/empty-annotations.yaml"

cp "$base_values" "$tmp/credential.yaml"
sed -i '/  existingSecret:/a\  secretAccessKey: plaintext-is-forbidden' "$tmp/credential.yaml"
expect_failure credential ./scripts/validate-chart.sh "$tmp/credential.yaml"

cp "$base_values" "$tmp/swapped-tags.yaml"
sed -i \
  -e 's/sha-0123456789abcdef0123456789abcdef01234567/sha-TEMP/' \
  -e 's/sha-89abcdef0123456789abcdef0123456789abcdef/sha-0123456789abcdef0123456789abcdef01234567/' \
  -e 's/sha-TEMP/sha-89abcdef0123456789abcdef0123456789abcdef/' \
  "$tmp/swapped-tags.yaml"
expect_failure swapped-tags ./scripts/validate-chart.sh "$tmp/swapped-tags.yaml"

cp -a charts/rgw-analysis-web "$tmp/forbidden"
printf '\n---\napiVersion: v1\nkind: Secret\nmetadata:\n  name: forbidden\n' >"$tmp/forbidden/templates/forbidden.yaml"
expect_failure forbidden env CHART_DIR="$tmp/forbidden" ./scripts/validate-chart.sh "$base_values"

cp -a charts/rgw-analysis-web "$tmp/selector"
sed -i '/include "rgw-analysis-web.selectorLabels"/c\    app.kubernetes.io/component: wrong' "$tmp/selector/templates/service.yaml"
expect_failure selector env CHART_DIR="$tmp/selector" ./scripts/validate-chart.sh "$base_values"

cp -a charts/rgw-analysis-web "$tmp/unsafe"
sed -i '/readOnlyRootFilesystem: true/d' "$tmp/unsafe/templates/_helpers.tpl"
expect_failure unsafe env CHART_DIR="$tmp/unsafe" ./scripts/validate-chart.sh "$base_values"

cp -a charts/rgw-analysis-web "$tmp/job-sync"
sed -i '/argocd.argoproj.io\/sync-options:/d' "$tmp/job-sync/templates/flow-jobs.yaml"
expect_failure job-sync env CHART_DIR="$tmp/job-sync" ./scripts/validate-chart.sh "$base_values"

cp -a charts/rgw-analysis-web "$tmp/token-mount"
sed -i '/automountServiceAccountToken: false/d' "$tmp/token-mount/templates/flow-jobs.yaml"
expect_failure token-mount env CHART_DIR="$tmp/token-mount" ./scripts/validate-chart.sh "$base_values"

echo "negative chart contracts: PASS"
