#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
entrypoint="$repo_root/scripts/validate-and-build.sh"
full_sha=0123456789abcdef0123456789abcdef01234567

test -x "$entrypoint" || {
  echo "missing production entrypoint: scripts/validate-and-build.sh" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fixture="$tmp/repository"
stub_bin="$tmp/bin"
log="$tmp/commands.log"
mkdir -p "$fixture/scripts" "$fixture/images" "$stub_bin"
cp "$entrypoint" "$fixture/scripts/validate-and-build.sh"
cp "$repo_root/images/docker-compose.build.yaml" "$fixture/images/docker-compose.build.yaml"

cat >"$fixture/scripts/test.sh" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
printf 'test %s\n' "$*" >>"$COMMAND_LOG"
STUB

cat >"$stub_bin/uv" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
command_line="uv $*"
printf '%s\n' "$command_line" >>"$COMMAND_LOG"
if [[ ${FAIL_ON:-} == "$command_line" ]]; then
  exit 23
fi
STUB

cat >"$stub_bin/git" <<STUB
#!/usr/bin/env bash
set -euo pipefail
printf 'git %s\n' "\$*" >>"\$COMMAND_LOG"
[[ \$# -eq 2 && \$1 == rev-parse && \$2 == HEAD ]] || {
  echo "unexpected git invocation: \$*" >&2
  exit 64
}
printf '%s\n' '$full_sha'
STUB

cat >"$stub_bin/docker" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
for argument in "$@"; do
  case "$argument" in
    push|login|logout)
      echo "forbidden docker operation: $argument" >&2
      exit 65
      ;;
  esac
done
printf 'docker FLOW_IMAGE_REPOSITORY=%s FLOW_IMAGE_TAG=%s WEB_IMAGE_REPOSITORY=%s WEB_IMAGE_TAG=%s :: %s\n' \
  "${FLOW_IMAGE_REPOSITORY:-}" "${FLOW_IMAGE_TAG:-}" \
  "${WEB_IMAGE_REPOSITORY:-}" "${WEB_IMAGE_TAG:-}" "$*" >>"$COMMAND_LOG"
STUB

chmod +x "$fixture/scripts/test.sh" "$stub_bin/uv" "$stub_bin/git" "$stub_bin/docker"

run_entrypoint() {
  (
    cd "$fixture"
    PATH="$stub_bin:/usr/bin:/bin" \
      COMMAND_LOG="$log" \
      FAIL_ON="${FAIL_ON:-}" \
      ./scripts/validate-and-build.sh
  )
}

assert_log_equals() {
  local expected=$1
  local actual
  actual="$(cat "$log")"
  [[ $actual == "$expected" ]] || {
    printf 'unexpected command log\n--- expected ---\n%s\n--- actual ---\n%s\n' \
      "$expected" "$actual" >&2
    exit 1
  }
}

validation_prefix=$(cat <<'EXPECTED'
uv lock --check
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
EXPECTED
)

# Given the fourth validation gate fails, When the entrypoint runs, Then it stops immediately.
: >"$log"
set +e
FAIL_ON='uv run --frozen ruff check .' run_entrypoint >/dev/null 2>&1
status=$?
set -e
[[ $status -eq 23 ]] || {
  echo "validation failure status was not preserved: $status" >&2
  exit 1
}
assert_log_equals "$validation_prefix"

# Given every gate succeeds, When the entrypoint runs, Then build and inspection follow validation.
: >"$log"
run_entrypoint >/dev/null
expected_success=$(cat <<EXPECTED
$validation_prefix
uv run --frozen basedpyright
test 
git rev-parse HEAD
docker FLOW_IMAGE_REPOSITORY=smurf-child-flow FLOW_IMAGE_TAG=sha-$full_sha WEB_IMAGE_REPOSITORY=smurf-child-web WEB_IMAGE_TAG=sha-$full_sha :: compose --env-file /dev/null -f images/docker-compose.build.yaml build
docker FLOW_IMAGE_REPOSITORY= FLOW_IMAGE_TAG= WEB_IMAGE_REPOSITORY= WEB_IMAGE_TAG= :: image inspect smurf-child-flow:sha-$full_sha smurf-child-web:sha-$full_sha
EXPECTED
)
assert_log_equals "$expected_success"

echo "validate-and-build contracts: PASS"
