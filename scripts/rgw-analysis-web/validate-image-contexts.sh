#!/usr/bin/env bash
set -euo pipefail

root=${1:-.}
flow="$root/images/rgw-analysis-web/flow/Containerfile"
web="$root/images/rgw-analysis-web/web/Containerfile"
assets="$root/src/rgw-analysis-web/web"

logical_instructions() {
  awk '
    { logical = logical $0 }
    /\\$/ { sub(/\\$/, "", logical); next }
    { print logical; logical = "" }
    END { if (logical != "") print logical }
  ' "$1"
}

validate_copy_set() {
  local file=$1
  shift
  local expected
  mapfile -t actual < <(logical_instructions "$file" | sed -n -E '/^[[:space:]]*COPY[[:space:]]+/I{s/^[[:space:]]+//;s/[[:space:]]+/ /g;s/[[:space:]]+$//;s/^[Cc][Oo][Pp][Yy]/COPY/;p}')
  test "${#actual[@]}" -eq "$#" || {
    echo "unexpected or duplicate COPY instruction in $file" >&2
    exit 1
  }
  for expected in "$@"; do
    test "$(printf '%s\n' "${actual[@]}" | grep -Fxc "$expected")" -eq 1 || {
      echo "required COPY binding is missing or drifted in $file" >&2
      exit 1
    }
  done
}

for path in \
  "$flow" \
  "$web" \
  "$root/images/rgw-analysis-web/web/nginx.conf" \
  "$assets/index.template.html" \
  "$assets/report.css" \
  "$assets/favicon.svg" \
  "$assets/fixtures/loading.html"; do
  test -s "$path" || { echo "missing image input: $path" >&2; exit 1; }
done

grep -Fq 'COPY --from=web-source index.template.html report.css favicon.svg /opt/smurf-flow/web/' "$flow"
grep -Fq 'SMURF_WEB_ASSETS_PATH=/opt/smurf-flow/web' "$flow"
grep -Fq 'COPY --from=web-source report.css favicon.svg /opt/viewer/assets/' "$web"
grep -Eq '^FROM ghcr\.io/astral-sh/uv:[0-9]+\.[0-9]+\.[0-9]+@sha256:[0-9a-f]{64} AS uv$' "$flow"
grep -Fq 'RUN uv sync --frozen --no-dev --no-editable' "$flow"
if logical_instructions "$flow" | rg -q -i '(^|[^[:alnum:]_])pip([0-9]+([.][0-9]+)*)?([^[:alnum:]_]|$)'; then
  echo "flow image contains an executable pip invocation" >&2
  exit 1
fi

mapfile -t definitions < <(find "$root/images/rgw-analysis-web" -type f \( -name Containerfile -o -name Dockerfile \) -print | sort)
for file in "${definitions[@]}"; do
  if logical_instructions "$file" | rg -q -i '^[[:space:]]*(ARG|ENV)[[:space:]].*(access[_-]?key|secret|credential|password|passwd|token|private[_-]?key|kubeconfig|aws_profile|AKIA[0-9A-Z]{16}|-----BEGIN.*PRIVATE KEY|://[^[:space:]/:@]+:[^[:space:]@]+@)'; then
    echo "credential-bearing image build argument or environment" >&2
    exit 1
  fi
  grep -Eq '^FROM [^[:space:]]+@sha256:[0-9a-f]{64}([[:space:]]|$)' "$file"
  grep -Eq '^USER [1-9][0-9]*(:[1-9][0-9]*)?$' "$file"
  if rg -n -i '(kubeconfig|kube[c]tl|karma[d]a|cluster-admin|:latest)' "$file"; then
    echo "unsafe image instruction" >&2
    exit 1
  fi
done

for component in flow web; do
  context="$root/images/rgw-analysis-web/$component"
  mapfile -t component_definitions < <(find "$context" -type f \( -name Containerfile -o -name Dockerfile \) -print | sort)
  test "${#component_definitions[@]}" -eq 1 || {
    echo "$component image context must contain exactly one build definition" >&2
    exit 1
  }
done

validate_copy_set "$flow" \
  'COPY --from=uv /uv /uvx /bin/' \
  'COPY --from=project-source pyproject.toml uv.lock ./' \
  'COPY --from=flow-source . src/rgw-analysis-web/flow/' \
  'COPY --from=builder /opt/venv /opt/venv' \
  'COPY --from=web-source index.template.html report.css favicon.svg /opt/smurf-flow/web/'
validate_copy_set "$web" \
  'COPY --from=web-source report.css favicon.svg /opt/viewer/assets/' \
  'COPY --from=web-source fixtures/loading.html /opt/viewer/bootstrap/index.html' \
  'COPY --from=web-source fixtures/loading.html /srv/viewer/current/index.html' \
  'COPY nginx.conf /etc/nginx/conf.d/default.conf'

echo "image context validation: PASS"
