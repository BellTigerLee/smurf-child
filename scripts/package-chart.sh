#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

source_epoch=${SOURCE_DATE_EPOCH:?set SOURCE_DATE_EPOCH}
source_revision=${SOURCE_REVISION:?set SOURCE_REVISION}
source_tree=${SOURCE_TREE:?set SOURCE_TREE}
flow_tag=${FLOW_IMAGE_TAG:?set FLOW_IMAGE_TAG}
flow_digest=${FLOW_IMAGE_DIGEST:?set FLOW_IMAGE_DIGEST}
flow_source_revision=${FLOW_SOURCE_REVISION:-$source_revision}
web_tag=${WEB_IMAGE_TAG:?set WEB_IMAGE_TAG}
web_digest=${WEB_IMAGE_DIGEST:?set WEB_IMAGE_DIGEST}
web_source_revision=${WEB_SOURCE_REVISION:-$source_revision}
ci_run_url=${CI_RUN_URL:?set CI_RUN_URL}

[[ $source_epoch =~ ^[0-9]+$ ]]
[[ $source_revision =~ ^[0-9a-f]{40}$ ]]
[[ $source_tree =~ ^[0-9a-f]{40}$ ]]
[[ $flow_source_revision =~ ^[0-9a-f]{40}$ ]]
[[ $web_source_revision =~ ^[0-9a-f]{40}$ ]]
[[ $flow_tag == "sha-$flow_source_revision" ]]
[[ $web_tag == "sha-$web_source_revision" ]]
[[ $flow_digest =~ ^sha256:[0-9a-f]{64}$ ]]
[[ $web_digest =~ ^sha256:[0-9a-f]{64}$ ]]
[[ $ci_run_url == https://github.com/*/actions/runs/* ]]

chart_dir=charts/rgw-analysis-web
version="$(awk '$1 == "version:" {print $2; exit}' "$chart_dir/Chart.yaml")"
output_dir=dist/rgw-analysis-web
package="$output_dir/rgw-analysis-web-$version.tgz"
mkdir -p "$output_dir"
rm -f "$package" "$output_dir/promotion.yaml"

tar \
  --sort=name \
  --mtime="@$source_epoch" \
  --owner=0 \
  --group=0 \
  --numeric-owner \
  --format=ustar \
  -C charts \
  -czf "$package" \
  rgw-analysis-web
package_digest="sha256:$(sha256sum "$package" | awk '{print $1}')"

cat >"$output_dir/promotion.yaml" <<EOF
apiVersion: scalex.io/promotion/v1
kind: PromotionArtifact
source:
  repository: https://github.com/BellTigerLee/smurf-child.git
  revision: $source_revision
  tree: $source_tree
chart:
  path: charts/rgw-analysis-web
  version: $version
  package: rgw-analysis-web-$version.tgz
  digest: $package_digest
components:
  flow:
    repository: ghcr.io/belltigerlee/smurf-child-flow
    sourceRevision: $flow_source_revision
    tag: $flow_tag
    digest: $flow_digest
  web:
    repository: ghcr.io/belltigerlee/smurf-child-web
    sourceRevision: $web_source_revision
    tag: $web_tag
    digest: $web_digest
ci:
  runUrl: $ci_run_url
EOF

echo "$package"
