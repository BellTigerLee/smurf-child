"""Namespace-neutral Kubernetes manifest admission."""

import re
from pathlib import Path
from typing import ClassVar, assert_never

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smurf_child.models import ContractErrorCategory, ContractValidationError
from smurf_child.yaml_boundary import JsonValue, load_yaml

_ALLOWED_KINDS = frozenset({"Deployment", "Service", "ConfigMap", "Job", "CronJob"})
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$", re.ASCII)


class Metadata(BaseModel):
    """Required Kubernetes metadata and forbidden namespace field."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="allow", strict=True
    )

    name: str
    namespace: str | None = None


class KubernetesObject(BaseModel):
    """Minimal typed Kubernetes object admission envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="allow", populate_by_name=True, strict=True
    )

    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: Metadata


def _walk_images(value: JsonValue, images: list[str]) -> None:
    match value:
        case dict() as mapping:
            image = mapping.get("image")
            if isinstance(image, str):
                images.append(image)
            for child in mapping.values():
                _walk_images(child, images)
        case list() as sequence:
            for child in sequence:
                _walk_images(child, images)
        case str() | int() | None:
            return
        case _ as unreachable:
            assert_never(unreachable)


def parse_manifest(path: Path) -> tuple[KubernetesObject, JsonValue, tuple[str, ...]]:
    """Parse one admitted resource and return every discovered image."""
    value = load_yaml(path, ContractErrorCategory.MANIFEST_MALFORMED)
    try:
        resource = KubernetesObject.model_validate(value)
    except ValidationError as error:
        raise ContractValidationError(
            ContractErrorCategory.MANIFEST_MALFORMED, path
        ) from error
    if resource.kind not in _ALLOWED_KINDS:
        raise ContractValidationError(ContractErrorCategory.FORBIDDEN_KIND, path)
    if resource.metadata.namespace is not None:
        raise ContractValidationError(ContractErrorCategory.FORBIDDEN_NAMESPACE, path)
    images: list[str] = []
    _walk_images(value, images)
    if any(_IMAGE.fullmatch(image) is None for image in images):
        raise ContractValidationError(ContractErrorCategory.IMMUTABLE_IMAGE, path)
    return resource, value, tuple(images)
