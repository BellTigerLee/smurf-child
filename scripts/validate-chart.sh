#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

helm_bin=${HELM_BIN:-helm}
chart_dir=${CHART_DIR:-charts/rgw-analysis-web}
values_file=${1:-${VALUES_FILE:-tests/rgw-analysis-web/fixtures/values.valid.yaml}}
command -v "$helm_bin" >/dev/null 2>&1 || { echo "helm is required" >&2; exit 1; }
test -f "$chart_dir/Chart.yaml"
test -f "$values_file"

if rg -n '^(kind:[[:space:]]*(Secret|ExternalSecret|Namespace|ClusterRole|ClusterRoleBinding|CustomResourceDefinition|PropagationPolicy|ClusterPropagationPolicy)|apiVersion:[[:space:]].*karmada\.io/)' "$chart_dir"; then
  echo "chart source contains a forbidden object" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
"$helm_bin" lint "$chart_dir" --strict --values "$values_file"
"$helm_bin" template contract "$chart_dir" \
  --namespace contract \
  --values "$values_file" >"$tmp/rendered.yaml"
./scripts/rgw-analysis-web/validate-render.sh "$tmp/rendered.yaml" "$chart_dir"
echo "chart validation: PASS"
