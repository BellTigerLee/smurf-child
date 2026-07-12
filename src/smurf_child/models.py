"""Frozen public models and typed contract failures."""

from enum import StrEnum, unique
from pathlib import Path
from typing import Annotated, ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict, Field

type DeveloperId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type ChildId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type WorkloadId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type EnvironmentId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,31}$")]
type Target = Literal["b", "c", "both"]


@unique
class ContractErrorCategory(StrEnum):
    """Closed fail-closed error categories exposed by the CLI."""

    REQUEST_NOT_FOUND = "REQUEST_NOT_FOUND"
    REQUEST_MALFORMED = "REQUEST_MALFORMED"
    REQUEST_SCHEMA = "REQUEST_SCHEMA"
    EFFECTIVE_POLICY = "EFFECTIVE_POLICY"
    MANIFEST_NOT_FOUND = "MANIFEST_NOT_FOUND"
    MANIFEST_MALFORMED = "MANIFEST_MALFORMED"
    FORBIDDEN_KIND = "FORBIDDEN_KIND"
    FORBIDDEN_NAMESPACE = "FORBIDDEN_NAMESPACE"
    IMMUTABLE_IMAGE = "IMMUTABLE_IMAGE"
    FORBIDDEN_FORMAT = "FORBIDDEN_FORMAT"
    EXACT_CHECKOUT = "EXACT_CHECKOUT"
    EVIDENCE_INPUT = "EVIDENCE_INPUT"


class ContractValidationError(Exception):
    """Typed validation failure with its offending path."""

    __slots__: ClassVar[tuple[str, ...]] = ("_category", "_path")

    def __init__(self, category: ContractErrorCategory, path: Path) -> None:
        """Create a categorized failure for one boundary path."""
        self._category: ContractErrorCategory = category
        self._path: Path = path
        super().__init__(str(self))

    @property
    def category(self) -> ContractErrorCategory:
        """Return the stable failure category."""
        return self._category

    @property
    def path(self) -> Path:
        """Return the offending boundary path."""
        return self._path

    @override
    def __str__(self) -> str:
        return f"{self.category.value}:{self.path.as_posix()}"


class ChildRequest(BaseModel):
    """Inert child request parsed at the file boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True, strict=True
    )

    api_version: Literal["smurfx.dev/v1alpha1"] = Field(alias="apiVersion")
    kind: Literal["ChildRequest"]
    developer_id: DeveloperId = Field(alias="developerId")
    child_id: ChildId = Field(alias="childId")
    workload_id: WorkloadId = Field(alias="workloadId")
    environment: EnvironmentId
    target: Target


class ManifestInventory(BaseModel):
    """Validated namespace-neutral child resource inventory."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    kinds: tuple[str, ...]
    images: tuple[str, ...]
    namespace_neutral: Literal[True]
    bundle_digest: str = ""


class RepositoryValidation(BaseModel):
    """Successful repository-level validation result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    request: ChildRequest
    manifests: ManifestInventory
