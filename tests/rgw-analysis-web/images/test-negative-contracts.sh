#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/images/rgw-analysis-web" "$tmp/src/rgw-analysis-web"
cp -a images/rgw-analysis-web/flow "$tmp/images/rgw-analysis-web/"
cp -a images/rgw-analysis-web/web "$tmp/images/rgw-analysis-web/"
cp -a src/rgw-analysis-web/web "$tmp/src/rgw-analysis-web/"
rm "$tmp/src/rgw-analysis-web/web/report.css"

if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp" >"$tmp/output" 2>&1; then
  echo "missing web asset unexpectedly passed" >&2
  exit 1
fi
grep -Fq 'missing image input:' "$tmp/output"

cp -a images/rgw-analysis-web "$tmp/loading-images"
mkdir -p "$tmp/loading-root/images" "$tmp/loading-root/src/rgw-analysis-web"
cp -a "$tmp/loading-images" "$tmp/loading-root/images/rgw-analysis-web"
cp -a src/rgw-analysis-web/web "$tmp/loading-root/src/rgw-analysis-web/"
rm "$tmp/loading-root/src/rgw-analysis-web/web/fixtures/loading.html"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/loading-root" >"$tmp/loading-output" 2>&1; then
  echo "missing loading asset unexpectedly passed" >&2
  exit 1
fi

for mutation in credential arg duplicate duplicate-credential; do
  mkdir -p "$tmp/$mutation-root/images" "$tmp/$mutation-root/src/rgw-analysis-web"
  cp -a images/rgw-analysis-web "$tmp/$mutation-root/images/"
  cp -a src/rgw-analysis-web/web "$tmp/$mutation-root/src/rgw-analysis-web/"
done

printf '\nENV AWS_SECRET_ACCESS_KEY embedded\n' >>"$tmp/credential-root/images/rgw-analysis-web/flow/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/credential-root" >"$tmp/credential-output" 2>&1; then
  echo "legacy credential ENV unexpectedly passed" >&2
  exit 1
fi
grep -Fq 'credential-bearing image build argument or environment' "$tmp/credential-output"

printf '\nARG API_TOKEN\n' >>"$tmp/arg-root/images/rgw-analysis-web/flow/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/arg-root" >"$tmp/arg-output" 2>&1; then
  echo "credential ARG unexpectedly passed" >&2
  exit 1
fi
grep -Fq 'credential-bearing image build argument or environment' "$tmp/arg-output"

cp "$tmp/duplicate-root/images/rgw-analysis-web/flow/Containerfile" "$tmp/duplicate-root/images/rgw-analysis-web/flow/Dockerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/duplicate-root" >"$tmp/duplicate-output" 2>&1; then
  echo "ambiguous duplicate Dockerfile unexpectedly passed" >&2
  exit 1
fi
grep -Fq 'must contain exactly one build definition' "$tmp/duplicate-output"

cp "$tmp/duplicate-credential-root/images/rgw-analysis-web/flow/Containerfile" "$tmp/duplicate-credential-root/images/rgw-analysis-web/flow/Dockerfile"
printf '\nENV AWS_SECRET_ACCESS_KEY embedded\n' >>"$tmp/duplicate-credential-root/images/rgw-analysis-web/flow/Dockerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/duplicate-credential-root" >"$tmp/duplicate-credential-output" 2>&1; then
  echo "credential-bearing duplicate Dockerfile unexpectedly passed" >&2
  exit 1
fi
grep -Fq 'credential-bearing image build argument or environment' "$tmp/duplicate-credential-output"

for mutation in loading-copy nginx-copy duplicate-copy lowercase-copy; do
  mkdir -p "$tmp/$mutation-root/images" "$tmp/$mutation-root/src/rgw-analysis-web"
  cp -a images/rgw-analysis-web "$tmp/$mutation-root/images/"
  cp -a src/rgw-analysis-web/web "$tmp/$mutation-root/src/rgw-analysis-web/"
done

sed -i 's#fixtures/loading.html#fixtures/missing.html#' "$tmp/loading-copy-root/images/rgw-analysis-web/web/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/loading-copy-root" >"$tmp/loading-copy-output" 2>&1; then
  echo "renamed loading COPY source unexpectedly passed" >&2
  exit 1
fi

sed -i 's#COPY nginx.conf#COPY missing.conf#' "$tmp/nginx-copy-root/images/rgw-analysis-web/web/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/nginx-copy-root" >"$tmp/nginx-copy-output" 2>&1; then
  echo "substituted nginx COPY source unexpectedly passed" >&2
  exit 1
fi

printf '\nCOPY nginx.conf /tmp/ambiguous.conf\n' >>"$tmp/duplicate-copy-root/images/rgw-analysis-web/web/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/duplicate-copy-root" >"$tmp/duplicate-copy-output" 2>&1; then
  echo "ambiguous duplicate COPY unexpectedly passed" >&2
  exit 1
fi

printf '\ncOpY nginx.conf /tmp/case-ambiguous.conf\n' >>"$tmp/lowercase-copy-root/images/rgw-analysis-web/web/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/lowercase-copy-root" >"$tmp/lowercase-copy-output" 2>&1; then
  echo "case-variant duplicate COPY unexpectedly passed" >&2
  exit 1
fi

for mutation in direct-pip option-pip continued-pip; do
  mkdir -p "$tmp/$mutation-root/images" "$tmp/$mutation-root/src/rgw-analysis-web"
  cp -a images/rgw-analysis-web "$tmp/$mutation-root/images/"
  cp -a src/rgw-analysis-web/web "$tmp/$mutation-root/src/rgw-analysis-web/"
done

printf '\nRUN pip install rogue-package\n' >>"$tmp/direct-pip-root/images/rgw-analysis-web/flow/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/direct-pip-root" >"$tmp/direct-pip-output" 2>&1; then
  echo "direct pip invocation unexpectedly passed" >&2
  exit 1
fi

printf '\nRUN python -m pip --no-cache-dir install rogue-package\n' >>"$tmp/option-pip-root/images/rgw-analysis-web/flow/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/option-pip-root" >"$tmp/option-pip-output" 2>&1; then
  echo "option-separated pip invocation unexpectedly passed" >&2
  exit 1
fi

printf '\nRUN python -m pip \\\n+  --no-cache-dir install rogue-package\n' >>"$tmp/continued-pip-root/images/rgw-analysis-web/flow/Containerfile"
if ./scripts/rgw-analysis-web/validate-image-contexts.sh "$tmp/continued-pip-root" >"$tmp/continued-pip-output" 2>&1; then
  echo "continued pip invocation unexpectedly passed" >&2
  exit 1
fi
echo "negative image contracts: PASS"
