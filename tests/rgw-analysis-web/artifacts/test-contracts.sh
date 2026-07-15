#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

required=(
  features.yaml
  images/rgw-analysis-web/flow/Containerfile
  images/rgw-analysis-web/web/Containerfile
  images/rgw-analysis-web/web/nginx.conf
  images/docker-compose.build.yaml
  images/docker-compose.yaml
  charts/rgw-analysis-web/Chart.yaml
  charts/rgw-analysis-web/values.yaml
  charts/rgw-analysis-web/values.schema.json
  scripts/test.sh
  scripts/validate-chart.sh
  scripts/package-chart.sh
)

for path in "${required[@]}"; do
  test -s "$path" || { echo "missing required artifact: $path" >&2; exit 1; }
done

grep -Fxq 'apiVersion: scalex.io/features/v1' features.yaml
grep -Fxq 'kind: FeatureRegistry' features.yaml
grep -Fxq '  - name: rgw-analysis-web' features.yaml
grep -Fxq '    renderer: helm/v1' features.yaml

if rg -n -i '(access[_-]?key|secret[_-]?key|password|kubeconfig)[[:space:]]*[:=][[:space:]]*[^$<{[:space:]]+' \
  features.yaml images charts | rg -v '\$\{' >/dev/null; then
  echo "possible embedded credential or kubeconfig" >&2
  exit 1
fi

if rg -n '(kind:[[:space:]]*(Secret|ExternalSecret|Namespace|ClusterRole|ClusterRoleBinding|CustomResourceDefinition|PropagationPolicy|ClusterPropagationPolicy)|apiVersion:[[:space:]].*karmada\.io)' charts/rgw-analysis-web; then
  echo "chart contains a forbidden secret or federation resource" >&2
  exit 1
fi

grep -Eq '^USER [1-9][0-9]*(:[1-9][0-9]*)?$' images/rgw-analysis-web/flow/Containerfile
grep -Eq '^USER [1-9][0-9]*(:[1-9][0-9]*)?$' images/rgw-analysis-web/web/Containerfile
grep -Fq 'SMURF_WEB_ASSETS_PATH=/opt/smurf-flow/web' images/rgw-analysis-web/flow/Containerfile
grep -Fq 'COPY --from=web-source index.template.html report.css favicon.svg /opt/smurf-flow/web/' images/rgw-analysis-web/flow/Containerfile
grep -Fq 'root /srv/viewer/current;' images/rgw-analysis-web/web/nginx.conf
grep -Fq 'COPY --from=web-source report.css favicon.svg' images/rgw-analysis-web/web/Containerfile
grep -Fq '      web: src/rgw-analysis-web/web' features.yaml
grep -Fq 'while true; do' charts/rgw-analysis-web/templates/deployment.yaml
grep -Fq 'argocd.argoproj.io/sync-options: Force=true,Replace=true' charts/rgw-analysis-web/templates/flow-jobs.yaml
test "$(rg -c 'automountServiceAccountToken: false' charts/rgw-analysis-web/templates/flow-jobs.yaml charts/rgw-analysis-web/templates/deployment.yaml | awk -F: '{total += $2} END {print total}')" -eq 2

echo "artifact contracts: PASS"
