#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

artifact=tests/rgw-analysis-web/ci/fixtures/promotion.yaml
flow_digest=sha256:1111111111111111111111111111111111111111111111111111111111111111
web_digest=sha256:2222222222222222222222222222222222222222222222222222222222222222

promote() {
  ./scripts/rgw-analysis-web/promote-release.sh \
    --flow-digest "$flow_digest" --web-digest "$web_digest" "$@"
}

tree_checksum() {
  local root=$1
  (
    cd "$root"
    while IFS= read -r -d '' path; do
      sha256sum "$path"
    done < <(find . -type f -print0 | sort -z)
  ) | sha256sum
}

make_federation_fixture() {
  local root=$1
  local poc="$root/releases/poc/rgw-analysis-web"
  local cuty="$root/releases/cuty/rgw-analysis-web"

  mkdir -p "$poc/dependencies" "$poc/karmada" "$cuty"
  cp tests/rgw-analysis-web/ci/fixtures/release.legacy-poc.yaml "$poc/release.yaml"
  cp tests/rgw-analysis-web/ci/fixtures/values.poc.yaml "$poc/values.yaml"
  cp tests/rgw-analysis-web/ci/fixtures/release.legacy-poc.yaml "$poc/dependencies/legacy.yaml"
  cp tests/rgw-analysis-web/ci/fixtures/release.legacy-poc.yaml "$poc/karmada/legacy.yaml"
  cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$cuty/release.yaml"
  cp tests/rgw-analysis-web/ci/fixtures/values.yaml "$cuty/values.yaml"
}

fixture="$tmp/federation"
make_federation_fixture "$fixture"
poc="$fixture/releases/poc/rgw-analysis-web"
cuty="$fixture/releases/cuty/rgw-analysis-web"
release="$cuty/release.yaml"
values="$cuty/values.yaml"
poc_before="$(tree_checksum "$poc")"

cuty_before="$(tree_checksum "$cuty")"
dry_run_output="$(promote --artifact "$artifact" --federation-dir "$fixture")"
test "$cuty_before" = "$(tree_checksum "$cuty")"
test "$poc_before" = "$(tree_checksum "$poc")"
grep -Fq 'dry-run' <<<"$dry_run_output"

promote --artifact "$artifact" --federation-dir "$fixture" --write
test "$poc_before" = "$(tree_checksum "$poc")"
grep -Fq 'environment: cuty' "$release"
grep -Fq 'namespace: scalex-cuty-rgw-analysis-web' "$release"
grep -Fq 'repoURL: https://github.com/BellTigerLee/smurf-child.git' "$release"
grep -Fq 'path: charts/rgw-analysis-web' "$release"
grep -Fq 'revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$release"
grep -Fq 'repository: ghcr.io/belltigerlee/smurf-child-flow' "$values"
grep -Fq 'tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$values"
grep -Fq 'digest: sha256:1111111111111111111111111111111111111111111111111111111111111111' "$values"
grep -Fq 'repository: ghcr.io/belltigerlee/smurf-child-web' "$values"
grep -Fq 'digest: sha256:2222222222222222222222222222222222222222222222222222222222222222' "$values"
test "$(grep -c 'sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$values")" -eq 2

cp tests/rgw-analysis-web/ci/fixtures/promotion.yaml "$fixture/local-unrelated-change.yaml"
promoted="$(tree_checksum "$cuty")"
dirty_before="$(sha256sum "$fixture/local-unrelated-change.yaml")"
promote --artifact "$artifact" --federation-dir "$fixture" --write
test "$promoted" = "$(tree_checksum "$cuty")"
test "$dirty_before" = "$(sha256sum "$fixture/local-unrelated-change.yaml")"
test "$poc_before" = "$(tree_checksum "$poc")"

transaction_fixture="$tmp/transaction-federation"
make_federation_fixture "$transaction_fixture"
transaction_before="$(tree_checksum "$transaction_fixture")"
if transaction_output="$(PROMOTION_TEST_FAIL_MOVE_INDEX=2 promote \
  --artifact "$artifact" --federation-dir "$transaction_fixture" --write 2>&1)"; then
  echo 'injected second replacement failure should fail' >&2
  exit 1
fi
test "$transaction_before" = "$(tree_checksum "$transaction_fixture")"
grep -Fq 'simulated replacement failure at move 2' <<<"$transaction_output"

symlink_outside="$tmp/symlink-outside"
symlink_ancestor_fixture="$tmp/symlink-ancestor-federation"
mkdir -p "$symlink_outside/rgw-analysis-web" "$symlink_ancestor_fixture/releases"
cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml \
  "$symlink_outside/rgw-analysis-web/release.yaml"
cp tests/rgw-analysis-web/ci/fixtures/values.yaml \
  "$symlink_outside/rgw-analysis-web/values.yaml"
ln -s "$symlink_outside" "$symlink_ancestor_fixture/releases/cuty"
symlink_outside_before="$(tree_checksum "$symlink_outside")"
if symlink_ancestor_output="$(promote --artifact "$artifact" \
  --federation-dir "$symlink_ancestor_fixture" --write 2>&1)"; then
  echo 'symlinked cuty ancestor should fail' >&2
  exit 1
fi
test "$symlink_outside_before" = "$(tree_checksum "$symlink_outside")"
grep -Fq 'unsafe symlink in Federation release path' <<<"$symlink_ancestor_output"

symlink_target_fixture="$tmp/symlink-target-federation"
make_federation_fixture "$symlink_target_fixture"
symlink_target_outside="$tmp/symlink-target-values.yaml"
cp "$symlink_target_fixture/releases/cuty/rgw-analysis-web/values.yaml" \
  "$symlink_target_outside"
rm "$symlink_target_fixture/releases/cuty/rgw-analysis-web/values.yaml"
ln -s "$symlink_target_outside" \
  "$symlink_target_fixture/releases/cuty/rgw-analysis-web/values.yaml"
symlink_target_before="$(sha256sum "$symlink_target_outside")"
if symlink_target_output="$(promote --artifact "$artifact" \
  --federation-dir "$symlink_target_fixture" --write 2>&1)"; then
  echo 'symlinked values target should fail' >&2
  exit 1
fi
test "$symlink_target_before" = "$(sha256sum "$symlink_target_outside")"
grep -Fq 'unsafe symlink in Federation release path' <<<"$symlink_target_output"

cp tests/rgw-analysis-web/ci/fixtures/release.pinned.yaml "$release"
pinned_before="$(tree_checksum "$cuty")"
promote --artifact "$artifact" --federation-dir "$fixture" --write
test "$pinned_before" = "$(tree_checksum "$cuty")"
test "$poc_before" = "$(tree_checksum "$poc")"

missing_fixture="$tmp/missing-cuty"
mkdir -p "$missing_fixture/releases/poc"
cp -R "$poc" "$missing_fixture/releases/poc/rgw-analysis-web"
missing_poc_before="$(tree_checksum "$missing_fixture/releases/poc/rgw-analysis-web")"
if missing_output="$(promote --artifact "$artifact" --federation-dir "$missing_fixture" --write 2>&1)"; then
  echo 'missing cuty target should fail' >&2
  exit 1
fi
test "$missing_poc_before" = "$(tree_checksum "$missing_fixture/releases/poc/rgw-analysis-web")"
grep -Fq 'missing Federation target' <<<"$missing_output"
if grep -Eq 'promotion mode|no Federation files changed' <<<"$missing_output"; then
  echo 'failed promotion emitted a misleading success message' >&2
  exit 1
fi

legacy_source_fixture="$tmp/legacy-source"
make_federation_fixture "$legacy_source_fixture"
legacy_source_release="$legacy_source_fixture/releases/cuty/rgw-analysis-web/release.yaml"
sed -i \
  -e 's#https://github.com/BellTigerLee/smurf-child.git#https://github.com/SJoon99/scalex-feature-poc.git#' \
  -e 's#path: charts/rgw-analysis-web#path: chart#' \
  "$legacy_source_release"
legacy_source_before="$(tree_checksum "$legacy_source_fixture")"
if legacy_output="$(promote --artifact "$artifact" --federation-dir "$legacy_source_fixture" --write 2>&1)"; then
  echo 'legacy scalex-feature-poc source should be rejected for cuty' >&2
  exit 1
fi
test "$legacy_source_before" = "$(tree_checksum "$legacy_source_fixture")"
grep -Eq 'unapproved current Federation source|unexpected Federation release' <<<"$legacy_output"
if grep -Eq 'promotion mode|no Federation files changed' <<<"$legacy_output"; then
  echo 'rejected legacy source emitted a misleading success message' >&2
  exit 1
fi

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
malformed="$tmp/malformed.yaml"
sed 's/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/tag: latest/' "$artifact" >"$malformed"
before="$(tree_checksum "$fixture")"
if malformed_output="$(promote --artifact "$malformed" --federation-dir "$fixture" --write 2>&1)"; then
  echo 'malformed promotion artifact should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"
grep -Fq 'invalid flow immutable tag' <<<"$malformed_output"

sed -i 's/namespace: scalex-cuty-rgw-analysis-web/namespace: stale-namespace/' "$release"
before="$(tree_checksum "$fixture")"
if stale_output="$(promote --artifact "$artifact" --federation-dir "$fixture" --write 2>&1)"; then
  echo 'stale cuty release identity should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"
grep -Fq 'unexpected Federation release namespace' <<<"$stale_output"

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
cp features.yaml "$tmp/features.yaml"
sed -i 's#renderer: helm/v1#renderer: raw/v1#' "$tmp/features.yaml"
before="$(tree_checksum "$fixture")"
if FEATURES_FILE="$tmp/features.yaml" promote \
  --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unknown renderer should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

sed 's#https://github.com/BellTigerLee/smurf-child.git#https://github.com/example/unapproved.git#' \
  "$artifact" >"$tmp/unapproved.yaml"
before="$(tree_checksum "$fixture")"
if promote --artifact "$tmp/unapproved.yaml" --federation-dir "$fixture" --write; then
  echo 'unapproved child origin should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

sed -i 's/renderer: helm\/v1/renderer: raw\/v1/' "$release"
before="$(tree_checksum "$fixture")"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unknown existing release renderer should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed -i 's/name: rgw-analysis-web/name: attacker-workload/' "$release"
before="$(tree_checksum "$fixture")"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'wrong existing release identity should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed -i 's#releases/cuty/rgw-analysis-web/karmada#../../.github/workflows#' "$release"
before="$(tree_checksum "$fixture")"
if promote --artifact "$artifact" --federation-dir "$fixture" --write; then
  echo 'unsafe existing policy path should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

cp tests/rgw-analysis-web/ci/fixtures/release.tracked.yaml "$release"
sed \
  -e "s/$flow_digest/swap-placeholder/" \
  -e "s/$web_digest/$flow_digest/" \
  -e "s/swap-placeholder/$web_digest/" \
  "$artifact" >"$tmp/swapped-digests.yaml"
before="$(tree_checksum "$fixture")"
if promote --artifact "$tmp/swapped-digests.yaml" --federation-dir "$fixture" --write; then
  echo 'component digest swap should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"

other_revision=dddddddddddddddddddddddddddddddddddddddd
sed \
  -e "0,/sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/{s/sourceRevision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/sourceRevision: $other_revision/}" \
  -e "0,/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/{s/tag: sha-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/tag: sha-$other_revision/}" \
  "$artifact" >"$tmp/component-source-mismatch.yaml"
before="$(tree_checksum "$fixture")"
if promote --artifact "$tmp/component-source-mismatch.yaml" --federation-dir "$fixture" --write; then
  echo 'component source revision mismatch should fail' >&2
  exit 1
fi
test "$before" = "$(tree_checksum "$fixture")"
test "$poc_before" = "$(tree_checksum "$poc")"

echo 'promotion contracts: PASS'
