#!/usr/bin/env bash
set -euo pipefail

default_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
root="$(cd "${1:-$default_root}" && pwd)"
git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo 'public artifact root must be a Git working tree' >&2
  exit 1
}

declare -a public_files=()
while IFS= read -r -d '' path; do
  if [[ -e "$root/$path" || -L "$root/$path" ]]; then
    public_files+=("$path")
  fi
done < <(git -C "$root" ls-files -z --cached --others --exclude-standard)

test "${#public_files[@]}" -gt 0 || {
  echo 'public artifact tree is empty' >&2
  exit 1
}

secret_path() {
  local path=${1,,}
  local base=${path##*/}

  case "$base" in
    .env|.env.*|*.kubeconfig|kubeconfig|kubeconfig.*|*.key|*.pem|*.p12|*.pfx|*.jks|*.keystore|*.der|*.crt|*.cer|id_rsa|id_rsa.*|id_ed25519|id_ed25519.*|.netrc|.npmrc|.pypirc|application_default_credentials.json|service-account*.json|service_account*.json)
      return 0
      ;;
  esac

  case "/$path/" in
    */.aws/*|*/.azure/*|*/.config/gcloud/*|*/.kube/*|*/.ssh/*)
      return 0
      ;;
  esac

  return 1
}

content_pattern='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|aws_(access_key_id|secret_access_key|session_token)[[:space:]]*[:=][[:space:]]*[^$<{[:space:]]+|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{20,})'
deployment_pattern='(kubectl[[:space:]]+apply|argocd[[:space:]]+app[[:space:]]+sync|karmada[^[:space:]]*[[:space:]]+apply)'

for path in "${public_files[@]}"; do
  if [[ -L "$root/$path" ]]; then
    printf 'tracked symlink is not allowed in the public artifact tree: %q\n' "$path" >&2
    exit 1
  fi
  if secret_path "$path"; then
    printf 'secret-prone tracked path is not allowed: %q\n' "$path" >&2
    exit 1
  fi
  if [[ -f "$root/$path" ]] && rg --quiet --hidden --ignore-case "$content_pattern" -- "$root/$path"; then
    printf 'credential-like content found in tracked path: %q\n' "$path" >&2
    exit 1
  fi
  case "$path" in
    .github/workflows/*|scripts/*)
      if [[ -f "$root/$path" ]] && rg --quiet "$deployment_pattern" -- "$root/$path"; then
        printf 'direct deployment command found in child automation: %q\n' "$path" >&2
        exit 1
      fi
      ;;
  esac
done

echo 'public artifact scan: PASS'
