#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

for script in scripts/test.sh scripts/validate-chart.sh scripts/package-chart.sh scripts/rgw-analysis-web/*.sh; do
  test -x "$script" || { echo "script is not executable: $script" >&2; exit 1; }
  bash -n "$script"
done

mutation_pattern='(^|[;&|[:space:]])(kubectl|karmada|argocd)([;&|[:space:]]|$)|(^|[;&|[:space:]])helm[[:space:]]+(install|upgrade)([;&|[:space:]]|$)'
if rg -n "$mutation_pattern" scripts; then
  echo "artifact scripts may not deploy or mutate clusters" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf '#!/usr/bin/env bash\nkubectl apply -f release.yaml\n' >"$tmp/deploy.sh"
if ! rg -q "$mutation_pattern" "$tmp/deploy.sh"; then
  echo "deployment mutation fixture was not rejected" >&2
  exit 1
fi

echo "script boundaries: PASS"
