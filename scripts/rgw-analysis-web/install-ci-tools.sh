#!/usr/bin/env bash
set -euo pipefail

destination=${1:?destination directory is required}
mkdir -p "$destination"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

helm_version=3.18.4
helm_archive="helm-v${helm_version}-linux-amd64.tar.gz"
helm_sha256=f8180838c23d7c7d797b208861fecb591d9ce1690d8704ed1e4cb8e2add966c1
curl --fail --silent --show-error --location \
  "https://get.helm.sh/${helm_archive}" --output "$tmp/$helm_archive"
printf '%s  %s\n' "$helm_sha256" "$tmp/$helm_archive" | sha256sum --check --status
tar -xzf "$tmp/$helm_archive" -C "$tmp"
install -m 0755 "$tmp/linux-amd64/helm" "$destination/helm"

actionlint_version=1.7.7
actionlint_archive="actionlint_${actionlint_version}_linux_amd64.tar.gz"
actionlint_sha256=023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757
curl --fail --silent --show-error --location \
  "https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}/${actionlint_archive}" \
  --output "$tmp/$actionlint_archive"
printf '%s  %s\n' "$actionlint_sha256" "$tmp/$actionlint_archive" | sha256sum --check --status
tar -xzf "$tmp/$actionlint_archive" -C "$tmp" actionlint
install -m 0755 "$tmp/actionlint" "$destination/actionlint"

if [[ -n ${GITHUB_PATH:-} ]]; then
  printf '%s\n' "$destination" >>"$GITHUB_PATH"
else
  printf 'add %s to PATH\n' "$destination"
fi
