#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

for workflow in .github/workflows/validate.yaml .github/workflows/publish-promote.yaml; do
  test -s "$workflow"
done

./scripts/rgw-analysis-web/validate_workflows.rb .

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
reset_workflows() {
  rm -rf "$tmp/.github/workflows"
  mkdir -p "$tmp/.github/workflows"
  cp .github/workflows/validate.yaml "$tmp/.github/workflows/validate.yaml"
  cp .github/workflows/publish-promote.yaml "$tmp/.github/workflows/publish-promote.yaml"
}
reset_workflows
sed -i -E '0,/@[0-9a-f]{40}/{s/@[0-9a-f]{40}/@v4/}' "$tmp/.github/workflows/validate.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'mutable action pin should fail' >&2
  exit 1
fi

validate=.github/workflows/validate.yaml
publish=.github/workflows/publish-promote.yaml
authority_fixture=tests/rgw-analysis-web/ci/fixtures/federation-authority.json
federation_authority="$(ruby -rjson -e '
  contract = JSON.parse(File.read(ARGV.fetch(0)))
  tower = contract.fetch("towerBootstrapSource")
  origin = contract.fetch("localOrigin")
  abort "Federation authorities drifted" unless tower == origin
  abort "unexpected Federation authority" unless tower == "https://github.com/SJoon99/scalex-federation.git"
  puts tower
' "$authority_fixture")"
federation_slug="${federation_authority#https://github.com/}"
federation_slug="${federation_slug%.git}"

grep -Fq 'pull_request:' "$validate"
grep -Fq 'contents: read' "$validate"
grep -Fq './scripts/test.sh' "$validate"
grep -Fq 'tests/rgw-analysis-web/artifacts/test-package.sh' scripts/test.sh
grep -Fq 'tests/rgw-analysis-web/ci/test-workflows.sh' "$validate"
grep -Fq 'tests/rgw-analysis-web/ci/test-public-scan.sh' "$validate"
grep -Fq 'tests/rgw-analysis-web/ci/test-public-scan.sh' "$publish"
grep -Fq './scripts/rgw-analysis-web/install-ci-tools.sh' "$validate"
grep -Fq 'actionlint_${actionlint_version}_linux_amd64.tar.gz' scripts/rgw-analysis-web/install-ci-tools.sh
grep -Fq '023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757' scripts/rgw-analysis-web/install-ci-tools.sh

grep -Fq 'branches:' "$publish"
grep -Fq -- '- main' "$publish"
if rg -n '(pull_request:|workflow_dispatch:|release/\*\*)' "$publish"; then
  echo 'registry-writing workflow must run only on a push to main' >&2
  exit 1
fi
grep -Fq 'build-flow:' "$publish"
grep -Fq 'build-web:' "$publish"
grep -Fq 'ghcr.io/belltigerlee/smurf-child-flow' "$publish"
grep -Fq 'ghcr.io/belltigerlee/smurf-child-web' "$publish"
grep -Fq 'sha-${GITHUB_SHA}' "$publish"
grep -Fq '[[ "${GITHUB_REF}" == '\''refs/heads/main'\'' ]]' "$publish"
grep -Fq 'SCALEX_PROMOTION_APP_ID' "$publish"
grep -Fq 'SCALEX_PROMOTION_APP_PRIVATE_KEY' "$publish"
grep -Fq "FEDERATION_GIT_URL: $federation_authority" "$publish"
grep -Fq "repository: $federation_slug" "$publish"
grep -Fq "TARGET_REPOSITORY: $federation_slug" "$publish"
grep -Fq 'owner: SJoon99' "$publish"
grep -Fq -- '--head "$BRANCH"' "$publish"
if grep -Fq 'BellTigerLee/scalex-federation' "$publish"; then
  echo 'promotion target must match the Tower-consumed Federation authority' >&2
  exit 1
fi
grep -Fq 'permission-contents: write' "$publish"
grep -Fq 'permission-pull-requests: write' "$publish"
grep -Fq 'automation/rgw-analysis-web' "$publish"
grep -Fq 'Manual protected merge is required.' "$publish"
grep -Fq 'scripts/rgw-analysis-web/promote-release.sh' "$publish"
grep -Fq 'packages: write' "$publish"
grep -Fq 'contents: read' "$publish"

if rg -n '(kubectl|karmada|argocd|SCALEX_RELEASE_KUBECONFIG|cluster-admin|auto[-_ ]?merge)' .github/workflows; then
  echo 'child workflow must stop at artifacts and a review PR' >&2
  exit 1
fi

if rg -n 'uses: [^[:space:]]+@(main|master|v[0-9]+([.]?[0-9]+)*)$' .github/workflows; then
  echo 'mutable action reference' >&2
  exit 1
fi

if rg -n -i '(private[_-]?key|password|access[_-]?key|secret[_-]?key):[[:space:]]+[^$<{[:space:]]+' .github/workflows docs README.md; then
  echo 'possible literal credential' >&2
  exit 1
fi

reset_workflows
sed -i '/^  push:$/i\  pull_request:' "$tmp/.github/workflows/publish-promote.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'PR-triggered publication should fail' >&2
  exit 1
fi

reset_workflows
sed -i '/runs-on: ubuntu-24.04/a\    env:\n      LEAK: ${{ secrets.SCALEX_PROMOTION_APP_PRIVATE_KEY }}' \
  "$tmp/.github/workflows/validate.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'PR secret access should fail' >&2
  exit 1
fi

reset_workflows
sed -i '/permission-pull-requests: write/a\          permission-actions: write' \
  "$tmp/.github/workflows/publish-promote.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'broader GitHub App permission should fail' >&2
  exit 1
fi

reset_workflows
sed -i 's/repositories: scalex-federation/repositories: scalex-federation,other/' \
  "$tmp/.github/workflows/publish-promote.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'broader GitHub App repository set should fail' >&2
  exit 1
fi

reset_workflows
sed -i 's#SJoon99/scalex-federation#BellTigerLee/scalex-federation#g; s/owner: SJoon99/owner: BellTigerLee/' \
  "$tmp/.github/workflows/publish-promote.yaml"
if ./scripts/rgw-analysis-web/validate_workflows.rb "$tmp"; then
  echo 'promotion authority drift should fail' >&2
  exit 1
fi

echo 'workflow contracts: PASS'
