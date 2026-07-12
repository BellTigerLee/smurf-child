"""Child request and manifest repository orchestration."""

from pathlib import Path

from pydantic import ValidationError

from smurf_child.bundle import build_bundle
from smurf_child.manifest import parse_manifest
from smurf_child.models import (
    ChildRequest,
    ContractErrorCategory,
    ContractValidationError,
    ManifestInventory,
    RepositoryValidation,
)
from smurf_child.yaml_boundary import load_yaml

_POLICY_FIELDS = frozenset(
    {
        "effectivePolicy",
        "effectiveTargets",
        "clusterNames",
        "placement",
        "propagationPolicy",
        "resourceBinding",
        "scheduling",
    }
)


def parse_request(path: Path) -> ChildRequest:
    """Parse one closed inert child request."""
    if not path.is_file():
        raise ContractValidationError(ContractErrorCategory.REQUEST_NOT_FOUND, path)
    value = load_yaml(path, ContractErrorCategory.REQUEST_MALFORMED)
    if isinstance(value, dict) and _POLICY_FIELDS.intersection(value):
        raise ContractValidationError(ContractErrorCategory.EFFECTIVE_POLICY, path)
    try:
        return ChildRequest.model_validate(value)
    except ValidationError as error:
        raise ContractValidationError(
            ContractErrorCategory.REQUEST_SCHEMA, path
        ) from error


def _manifest_files(path: Path) -> tuple[Path, ...]:
    if not path.exists():
        raise ContractValidationError(ContractErrorCategory.MANIFEST_NOT_FOUND, path)
    if path.is_file():
        if path.suffix != ".yaml":
            raise ContractValidationError(ContractErrorCategory.FORBIDDEN_FORMAT, path)
        return (path,)
    files = tuple(sorted(path.iterdir(), key=lambda item: item.name.encode("utf-8")))
    if not files:
        raise ContractValidationError(ContractErrorCategory.MANIFEST_NOT_FOUND, path)
    if any(
        file.suffix != ".yaml" or not file.is_file() or file.is_symlink()
        for file in files
    ):
        raise ContractValidationError(ContractErrorCategory.FORBIDDEN_FORMAT, path)
    return files


def validate_manifests(path: Path) -> ManifestInventory:
    """Validate plain YAML resources and collect all immutable images."""
    files = _manifest_files(path)
    kinds: list[str] = []
    images: list[str] = []
    for file in files:
        resource, _, resource_images = parse_manifest(file)
        kinds.append(resource.kind)
        images.extend(resource_images)
    digest = ""
    if path.is_dir() and path.parts[-2:] == ("deploy", "dev"):
        root = path.parent.parent
        relative = tuple(file.relative_to(root).as_posix() for file in files)
        digest = build_bundle(root, relative).digest
    return ManifestInventory(
        kinds=tuple(sorted(kinds)),
        images=tuple(sorted(images)),
        namespace_neutral=True,
        bundle_digest=digest,
    )


def validate_repository(root: Path) -> RepositoryValidation:
    """Validate the request and development bundle under one root."""
    manifests = validate_manifests(root / "deploy" / "dev")
    return RepositoryValidation(
        request=parse_request(root / "smurfx" / "request.yaml"),
        manifests=manifests,
    )
