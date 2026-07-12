set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

sync:
    uv lock --check
    uv sync --frozen

lint:
    uv run --frozen ruff format --check .
    uv run --frozen ruff check .
    uv run --frozen basedpyright
    uv run --frozen pytest

validate: sync lint
    uv run --frozen smurf-child validate --root .
