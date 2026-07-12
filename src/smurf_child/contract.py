"""Nonfunctional contract API reserved for Task 4."""

from pathlib import Path
from typing import Never


def _planned(category: str) -> Never:
    message = f"PLANNED_UNIMPLEMENTED:{category}"
    raise NotImplementedError(message)


def parse_request(path: Path, *, behavior: str = "request_schema") -> Never:
    """Expose the future request parser without implementing Task 4 behavior."""
    del path
    categories = {
        "request_schema": "REQUEST_SCHEMA",
        "stable_ids": "STABLE_IDS",
        "target_literal": "TARGET_LITERAL",
        "effective_policy": "EFFECTIVE_POLICY",
    }
    _planned(categories[behavior])


def validate_manifests(path: Path, *, behavior: str = "manifest_set") -> Never:
    """Expose the future manifest validator without implementing Task 4 behavior."""
    del path
    categories = {
        "manifest_set": "MANIFEST_SET",
        "immutable_image": "IMMUTABLE_IMAGE",
        "forbidden_format": "FORBIDDEN_FORMAT",
        "forbidden_kind": "FORBIDDEN_KIND",
    }
    _planned(categories[behavior])
