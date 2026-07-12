"""Fail-closed feature-branch handoff policy."""

from enum import StrEnum, unique
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

MAX_PYTHON_LOC = 250


@unique
class HandoffCategory(StrEnum):
    """Named unsafe handoff states."""

    DIRECT_MAIN = "DIRECT_MAIN"
    MERGE_OPERATION = "MERGE_OPERATION"
    BROAD_STAGING = "BROAD_STAGING"
    PRIVATE_MATERIAL = "PRIVATE_MATERIAL"
    EXCLUDED_REPO_DIFF = "EXCLUDED_REPO_DIFF"
    PYTHON_LOC = "PYTHON_LOC"
    STALE_SCHEMA = "STALE_SCHEMA"
    FIXTURE_SHA = "FIXTURE_SHA"


class HandoffState(BaseModel):
    """Measured local facts supplied to the pre-network guard."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    destination_ref: str
    operations: tuple[str, ...]
    staged_paths: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    excluded_repo_changes: tuple[str, ...]
    authored_python_loc: tuple[tuple[str, int], ...]
    schema_current: bool
    expected_fixture_sha: str
    fixture_sha: str


class HandoffRejection(BaseModel):
    """One stable reason that blocks a handoff."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    category: HandoffCategory


def evaluate_handoff(state: HandoffState) -> HandoffRejection | None:
    """Return the first unsafe state before any network write."""
    broad_staging = bool(set(state.staged_paths) & {".", "*", "--all"}) or not set(
        state.staged_paths
    ) <= set(state.allowed_paths)
    rules = (
        (
            state.destination_ref
            in {"main", "refs/heads/main", "ops", "refs/heads/ops"},
            HandoffCategory.DIRECT_MAIN,
        ),
        (bool(set(state.operations) - {"push"}), HandoffCategory.MERGE_OPERATION),
        (broad_staging, HandoffCategory.BROAD_STAGING),
        (bool(state.sensitive_paths), HandoffCategory.PRIVATE_MATERIAL),
        (bool(state.excluded_repo_changes), HandoffCategory.EXCLUDED_REPO_DIFF),
        (
            any(lines > MAX_PYTHON_LOC for _path, lines in state.authored_python_loc),
            HandoffCategory.PYTHON_LOC,
        ),
        (not state.schema_current, HandoffCategory.STALE_SCHEMA),
        (state.fixture_sha != state.expected_fixture_sha, HandoffCategory.FIXTURE_SHA),
    )
    category = next((category for rejected, category in rules if rejected), None)
    return None if category is None else HandoffRejection(category=category)
