"""Namespace-neutral Kubernetes manifest admission."""

import re
from pathlib import Path
from typing import ClassVar, Literal, TypeIs, assert_never

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smurf_child.models import ContractErrorCategory, ContractValidationError
from smurf_child.yaml_boundary import JsonValue, load_yaml

type AllowedKind = Literal["Deployment", "Service", "ConfigMap", "Job", "CronJob"]
_ALLOWED_KINDS: frozenset[AllowedKind] = frozenset(
    {"Deployment", "Service", "ConfigMap", "Job", "CronJob"}
)
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


def _required_mapping(value: JsonValue, key: str, path: Path) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ContractValidationError(ContractErrorCategory.IMMUTABLE_IMAGE, path)
    child = value.get(key)
    if not isinstance(child, dict):
        raise ContractValidationError(ContractErrorCategory.IMMUTABLE_IMAGE, path)
    return child


def _is_allowed_kind(value: str) -> TypeIs[AllowedKind]:
    return value in _ALLOWED_KINDS


def _pod_spec(
    kind: AllowedKind, value: JsonValue, path: Path
) -> dict[str, JsonValue] | None:
    match kind:
        case "Deployment" | "Job":
            spec = _required_mapping(value, "spec", path)
            template = _required_mapping(spec, "template", path)
            return _required_mapping(template, "spec", path)
        case "CronJob":
            spec = _required_mapping(value, "spec", path)
            job = _required_mapping(spec, "jobTemplate", path)
            job_spec = _required_mapping(job, "spec", path)
            template = _required_mapping(job_spec, "template", path)
            return _required_mapping(template, "spec", path)
        case "Service" | "ConfigMap":
            return None
        case _ as unreachable:
            assert_never(unreachable)


def _validate_container_images(
    pod_spec: dict[str, JsonValue], path: Path
) -> tuple[str, ...]:
    images: list[str] = []
    for field in ("containers", "initContainers", "ephemeralContainers"):
        containers = pod_spec.get(field)
        if containers is None:
            if field == "containers":
                raise ContractValidationError(
                    ContractErrorCategory.IMMUTABLE_IMAGE, path
                )
            continue
        if not isinstance(containers, list) or not containers:
            raise ContractValidationError(ContractErrorCategory.IMMUTABLE_IMAGE, path)
        for container in containers:
            if not isinstance(container, dict):
                raise ContractValidationError(
                    ContractErrorCategory.IMMUTABLE_IMAGE, path
                )
            image = container.get("image")
            if not isinstance(image, str) or _IMAGE.fullmatch(image) is None:
                raise ContractValidationError(
                    ContractErrorCategory.IMMUTABLE_IMAGE, path
                )
            images.append(image)
    return tuple(images)


def parse_manifest(path: Path) -> tuple[KubernetesObject, JsonValue, tuple[str, ...]]:
    """Parse one admitted resource and return every discovered image."""
    value = load_yaml(path, ContractErrorCategory.MANIFEST_MALFORMED)
    try:
        resource = KubernetesObject.model_validate(value)
    except ValidationError as error:
        raise ContractValidationError(
            ContractErrorCategory.MANIFEST_MALFORMED, path
        ) from error
    if not _is_allowed_kind(resource.kind):
        raise ContractValidationError(ContractErrorCategory.FORBIDDEN_KIND, path)
    if resource.metadata.namespace is not None:
        raise ContractValidationError(ContractErrorCategory.FORBIDDEN_NAMESPACE, path)
    pod_spec = _pod_spec(resource.kind, value, path)
    if pod_spec is None:
        images: list[str] = []
        _walk_images(value, images)
        if images:
            raise ContractValidationError(ContractErrorCategory.IMMUTABLE_IMAGE, path)
        return resource, value, ()
    return resource, value, _validate_container_images(pod_spec, path)
