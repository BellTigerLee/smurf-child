#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fixture="$tmp/federation"
mkdir -p "$fixture/releases/poc/rgw-analysis-web"
cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml \
  "$fixture/releases/poc/rgw-analysis-web/release.yaml"
cp tests/rgw-analysis-web/ci/fixtures/values.yaml \
  "$fixture/releases/poc/rgw-analysis-web/values.yaml"

artifact=tests/rgw-analysis-web/ci/fixtures/promotion.yaml
flow_digest=sha256:1111111111111111111111111111111111111111111111111111111111111111
web_digest=sha256:2222222222222222222222222222222222222222222222222222222222222222
promote() {
  ./scripts/rgw-analysis-web/promote-release.sh \
    --flow-digest "$flow_digest" --web-digest "$web_digest" "$@"
}
before="$(sha256sum "$fixture/releases/poc/rgw-analysis-web/"*.yaml)"
promote --artifact "$artifact" --federation-dir "$fixture"
test "$before" = "$(sha256sum "$fixture/releases/poc/rgw-analysis-web/"*.yaml)"

legacy_fixture="$tmp/legacy-federation"
mkdir -p "$legacy_fixture/releases/poc/rgw-analysis-web"
cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml \
  "$legacy_fixture/releases/poc/rgw-analysis-web/release.yaml"
cp tests/rgw-analysis-web/ci/fixtures/values.poc.yaml \
  "$legacy_fixture/releases/poc/rgw-analysis-web/values.yaml"
promote --artifact "$artifact" --federation-dir "$legacy_fixture" --write
legacy_values="$legacy_fixture/releases/poc/rgw-analysis-web/values.yaml"
grep -Fq 'runId: poc-rgw-analysis-web' "$legacy_values"
grep -Fq 'endpointUrl: http://10.33.142.10' "$legacy_values"
grep -Fq 'existingSecret: scalex-poc-rgw' "$legacy_values"
grep -Fq 'intervalSeconds: 10' "$legacy_values"
grep -Fq 'scalex.io/exposure: internal' "$legacy_values"
test "$(grep -c 'sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$legacy_values")" -eq 2
if grep -Eq 'releaseLabel:|awsCli:|nginx:|resultWeb:|inputKey:|resultPrefix:' "$legacy_values"; then
  echo 'legacy POC-only values survived the child promotion' >&2
  exit 1
fi

promote --artifact "$artifact" --federation-dir "$fixture" --write

release="$fixture/releases/poc/rgw-analysis-web/release.yaml"
values="$fixture/releases/poc/rgw-analysis-web/values.yaml"
grep -Fq 'renderer: helm/v1' "$release"
grep -Fq 'repoURL: https://github.com/BellTigerLee/smurf-child.git' "$release"
grep -Fq 'path: charts/rgw-analysis-web' "$release"
grep -Fq 'revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$release"
grep -Fq 'repository: ghcr.io/belltigerlee/smurf-child-flow' "$values"
grep -Fq 'tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$values"
grep -Fq 'digest: sha256:1111111111111111111111111111111111111111111111111111111111111111' "$values"
grep -Fq 'repository: ghcr.io/belltigerlee/smurf-child-web' "$values"
grep -Fq 'digest: sha256:2222222222222222222222222222222222222222222222222222222222222222' "$values"
test "$(grep -c 'sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$values")" -eq 2
promoted="$(sha256sum "$release" "$values")"
promote --artifact "$artifact" --federation-dir "$fixture" --write
test "$promoted" = "$(sha256sum "$release" "$values")"

cp tests/rgw-analysis-web/ci/fixtures/release.pinned.yaml "$release"
before="$(sha256sum "$release" "$values")"
promote --artifact "$artifact" --federation-dir "$fixture" --write
test "$before" = "$(sha256sum "$release" "$values")"

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
cp features.yaml "$tmp/features.yaml"
sed -i 's#renderer: helm/v1#renderer: raw/v1#' "$tmp/features.yaml"
before="$(sha256sum "$release" "$values")"
if FEATURES_FILE="$tmp/features.yaml" promote \
  --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unknown renderer should fail' >&2
  exit 1
fi
test "$before" = "$(sha256sum "$release" "$values")"

sed 's/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/tag: latest/' "$artifact" >"$tmp/latest.yaml"
if promote \
  --artifact "$tmp/latest.yaml" --federation-dir "$fixture" --write; then
  echo 'latest must never be promoted' >&2
  exit 1
fi

sed 's#https://github.com/BellTigerLee/smurf-child.git#https://github.com/example/unapproved.git#' \
  "$artifact" >"$tmp/unapproved.yaml"
if promote \
  --artifact "$tmp/unapproved.yaml" --federation-dir "$fixture" --write; then
  echo 'unapproved child origin should fail' >&2
  exit 1
fi

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed -i 's/renderer: helm\/v1/renderer: raw\/v1/' "$release"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unknown existing release renderer should fail' >&2
  exit 1
fi

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed -i 's/name: rgw-analysis-web/name: attacker-workload/' "$release"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'wrong existing release identity should fail' >&2
  exit 1
fi

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed -i 's#releases/poc/rgw-analysis-web/karmada#../../.github/workflows#' "$release"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unsafe existing policy path should fail' >&2
  exit 1
fi

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed \
  -e "s/$flow_digest/swap-placeholder/" \
  -e "s/$web_digest/$flow_digest/" \
  -e "s/swap-placeholder/$web_digest/" \
  "$artifact" >"$tmp/swapped-digests.yaml"
if promote --artifact "$tmp/swapped-digests.yaml" --federation-dir "$fixture" --write; then
  echo 'component digest swap should fail' >&2
  exit 1
fi

other_revision=dddddddddddddddddddddddddddddddddddddddd
sed \
  -e "0,/sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/{s/sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/sourceRevision: $other_revision/}" \
  -e "0,/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/{s/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/tag: sha-$other_revision/}" \
  "$artifact" >"$tmp/component-source-mismatch.yaml"
if promote --artifact "$tmp/component-source-mismatch.yaml" --federation-dir "$fixture" --write; then
  echo 'component source revision mismatch should fail' >&2
  exit 1
fi

echo 'promotion contracts: PASS'
