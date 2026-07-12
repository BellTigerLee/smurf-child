"""Frozen child contract boundary models reserved for Task 4."""

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
    """Closed validation categories expected from the future implementation."""

    REQUEST_NOT_FOUND = "REQUEST_NOT_FOUND"
    REQUEST_MALFORMED = "REQUEST_MALFORMED"
    REQUEST_SCHEMA = "REQUEST_SCHEMA"
    EFFECTIVE_POLICY = "EFFECTIVE_POLICY"
    MANIFEST_NOT_FOUND = "MANIFEST_NOT_FOUND"
    MANIFEST_MALFORMED = "MANIFEST_MALFORMED"
    FORBIDDEN_KIND = "FORBIDDEN_KIND"
    IMMUTABLE_IMAGE = "IMMUTABLE_IMAGE"
    FORBIDDEN_FORMAT = "FORBIDDEN_FORMAT"


@unique
class PlannedBoundary(StrEnum):
    """Unimplemented Task 4 boundaries, selected only by the called API."""

    REQUEST_PARSER = "REQUEST_PARSER"
    MANIFEST_VALIDATOR = "MANIFEST_VALIDATOR"
    REPOSITORY_VALIDATOR = "REPOSITORY_VALIDATOR"


class PlannedBehaviorError(NotImplementedError):
    """Signal that a concrete Task 4 boundary remains intentionally RED."""

    __slots__: ClassVar[tuple[str, ...]] = ("_boundary",)
    _boundary: PlannedBoundary

    def __init__(self, boundary: PlannedBoundary) -> None:
        """Initialize an unimplemented boundary signal."""
        self._boundary = boundary
        super().__init__(str(self))

    @property
    def boundary(self) -> PlannedBoundary:
        """Return the API boundary that remains unimplemented."""
        return self._boundary

    @override
    def __str__(self) -> str:
        """Render the stable RED inventory signature."""
        return f"PLANNED_UNIMPLEMENTED:{self.boundary.value}"


class ContractValidationError(Exception):
    """Future typed validation failure exposed to tests and the CLI."""

    __slots__: ClassVar[tuple[str, ...]] = ("_category", "_path")
    _category: ContractErrorCategory
    _path: Path

    def __init__(self, category: ContractErrorCategory, path: Path) -> None:
        """Initialize a future categorized validation failure."""
        self._category = category
        self._path = path
        super().__init__(str(self))

    @property
    def category(self) -> ContractErrorCategory:
        """Return the exact future validation category."""
        return self._category

    @property
    def path(self) -> Path:
        """Return the input path that failed validation."""
        return self._path

    @override
    def __str__(self) -> str:
        """Render the category and repository-relative input path."""
        return f"{self.category.value}:{self.path.as_posix()}"


class ChildRequest(BaseModel):
    """Future child-to-federation request boundary shape."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    api_version: Literal["smurfx.dev/v1alpha1"] = Field(alias="apiVersion")
    kind: Literal["ChildRequest"]
    developer_id: DeveloperId = Field(alias="developerId")
    child_id: ChildId = Field(alias="childId")
    workload_id: WorkloadId = Field(alias="workloadId")
    environment: EnvironmentId
    target: Target


class ManifestInventory(BaseModel):
    """Future validated inventory of namespace-neutral child resources."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    kinds: tuple[str, ...]
    images: tuple[str, ...]
    namespace_neutral: bool


class RepositoryValidation(BaseModel):
    """Future successful repository-level validation result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    request: ChildRequest
    manifests: ManifestInventory
