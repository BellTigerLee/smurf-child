set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

sync:
    uv lock --check
    uv sync --frozen

lint:
    uv run --frozen ruff format --check .
    uv run --frozen ruff check .
    uv run --frozen basedpyright
    uv run --frozen pytest -q tests/test_red_contract_runner.py

red-contract:
    uv run --frozen smurf-child-red-contract

validate: sync lint red-contract
