#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
scanner="$repo_root/scripts/rgw-analysis-web/scan-public-artifacts.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fixture="$tmp/public-tree"

ignore_files=(
  .gitignore
  .dockerignore
  images/rgw-analysis-web/flow/.dockerignore
  images/rgw-analysis-web/web/.dockerignore
  src/rgw-analysis-web/flow/.dockerignore
  src/rgw-analysis-web/web/.dockerignore
)
for ignore_file in "${ignore_files[@]}"; do
  test -s "$repo_root/$ignore_file"
  grep -Fq '**/.env*' "$repo_root/$ignore_file"
  grep -Fq '**/kubeconfig*' "$repo_root/$ignore_file"
  grep -Fq '**/*.key' "$repo_root/$ignore_file"
  grep -Fq '**/.aws/**' "$repo_root/$ignore_file"
  grep -Fq '**/.config/gcloud/**' "$repo_root/$ignore_file"
done

reset_fixture() {
  rm -rf "$fixture"
  mkdir -p "$fixture"
  git -C "$fixture" init --quiet
  printf '%s\n' 'public source' >"$fixture/README.md"
  git -C "$fixture" add README.md
}

expect_filename_rejection() {
  local path=$1
  reset_fixture
  mkdir -p "$(dirname "$fixture/$path")"
  printf '%s\n' 'not-a-real-credential' >"$fixture/$path"
  git -C "$fixture" add --force "$path"
  if "$scanner" "$fixture" >/dev/null 2>&1; then
    echo "secret-prone tracked path was accepted: $path" >&2
    exit 1
  fi
}

reset_fixture
"$scanner" "$fixture" >/dev/null

expect_filename_rejection .env
expect_filename_rejection nested/.env.production
expect_filename_rejection config/team/kubeconfig
expect_filename_rejection credentials/client.key
expect_filename_rejection cloud/.aws/credentials
expect_filename_rejection cloud/.config/gcloud/application_default_credentials.json

reset_fixture
mkdir -p "$fixture/config"
printf '%s%s\n' '-----BEGIN ' 'PRIVATE KEY-----' >"$fixture/config/public.txt"
git -C "$fixture" add config/public.txt
if "$scanner" "$fixture" >/dev/null 2>&1; then
  echo 'private-key signature was accepted' >&2
  exit 1
fi

reset_fixture
mkdir -p "$fixture/config"
printf '%s%s\n' 'aws_secret_' 'access_key=fixture-not-real' >"$fixture/config/runtime.txt"
git -C "$fixture" add config/runtime.txt
if "$scanner" "$fixture" >/dev/null 2>&1; then
  echo 'cloud credential assignment was accepted' >&2
  exit 1
fi

echo 'full public-tree scan contracts: PASS'
