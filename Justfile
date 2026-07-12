set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

sync:
    uv sync --frozen

lint:
    uv run --frozen ruff format --check .
    uv run --frozen ruff check .
    uv run --frozen basedpyright

red-contract:
    #!/usr/bin/env bash
    set +e
    output="$(uv run --frozen pytest -q tests/test_request_contract.py tests/test_manifest_contract.py tests/test_cli.py tests/test_red_fixtures.py 2>&1)"
    status=$?
    set -e
    printf '%s\n' "$output"
    test "$status" -ne 0
    grep -q 'PLANNED_UNIMPLEMENTED:' <<<"$output"

validate: sync lint red-contract
