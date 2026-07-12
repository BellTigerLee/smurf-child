"""Nonfunctional contract APIs reserved for Task 4."""

from pathlib import Path

from smurf_child.models import (
    ChildRequest,
    ManifestInventory,
    PlannedBehaviorError,
    PlannedBoundary,
    RepositoryValidation,
)


def parse_request(path: Path) -> ChildRequest:
    """Parse a real request path when Task 4 implements the boundary."""
    del path
    raise PlannedBehaviorError(boundary=PlannedBoundary.REQUEST_PARSER)


def validate_manifests(path: Path) -> ManifestInventory:
    """Validate a real manifest path when Task 4 implements the boundary."""
    del path
    raise PlannedBehaviorError(boundary=PlannedBoundary.MANIFEST_VALIDATOR)


def validate_repository(root: Path) -> RepositoryValidation:
    """Validate a real repository root when Task 4 implements the boundary."""
    del root
    raise PlannedBehaviorError(boundary=PlannedBoundary.REPOSITORY_VALIDATOR)
