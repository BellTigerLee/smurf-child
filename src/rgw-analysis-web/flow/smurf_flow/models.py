"""Validated flow boundary models and immutable run paths."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Annotated, ClassVar, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

RunId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"),
]
SCHEMA_VERSION: Final = "smurf-rgw-analysis/v1"
BASE_PREFIX: Final = "smurf-rgw-analysis/v1/runs"
DEFAULT_WEB_ASSETS_PATH: Final = Path("/opt/smurf-flow/web")


class StorageSettings(BaseSettings):
    """Non-secret S3 configuration parsed from the runtime environment."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        frozen=True,
        extra="ignore",
    )

    endpoint_url: str = Field(min_length=1, validation_alias="S3_ENDPOINT_URL")
    bucket: str = Field(min_length=3, validation_alias="S3_BUCKET")
    region: str = Field(
        default="us-east-1",
        min_length=1,
        validation_alias="AWS_DEFAULT_REGION",
    )
    wait_seconds: float = Field(
        default=120.0,
        gt=0,
        validation_alias="S3_WAIT_SECONDS",
    )
    poll_interval_seconds: float = Field(
        default=2.0,
        gt=0,
        validation_alias="S3_POLL_INTERVAL_SECONDS",
    )


class WebAssetSettings(BaseSettings):
    """Absolute runtime location of the Todo 3 static viewer assets."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        frozen=True,
        extra="ignore",
    )

    directory: Path = Field(
        default=DEFAULT_WEB_ASSETS_PATH,
        validation_alias="SMURF_WEB_ASSETS_PATH",
    )

    @field_validator("directory")
    @classmethod
    def directory_is_absolute(cls, value: Path) -> Path:
        """Reject process-working-directory-dependent asset lookup."""
        if not value.is_absolute():
            msg = "web asset directory must be absolute"
            raise ValueError(msg)
        return value


@dataclass(frozen=True, slots=True)
class RunPaths:
    """Canonical keys for one immutable analysis run."""

    run_id: RunId

    @property
    def root(self) -> str:
        """Return the immutable run root."""
        return f"{BASE_PREFIX}/{self.run_id}"

    @property
    def input_prefix(self) -> str:
        """Return the run input prefix."""
        return f"{self.root}/input/"

    @property
    def dataset(self) -> str:
        """Return the canonical seeded dataset key."""
        return f"{self.input_prefix}dataset.csv"

    @property
    def input_marker(self) -> str:
        """Return the input commit marker key."""
        return f"{self.input_prefix}_SUCCESS.json"

    @property
    def output_prefix(self) -> str:
        """Return the run output prefix."""
        return f"{self.root}/output/"

    @property
    def result(self) -> str:
        """Return the canonical JSON result key."""
        return f"{self.output_prefix}result.json"

    @property
    def index(self) -> str:
        """Return the canonical static viewer key."""
        return f"{self.output_prefix}index.html"

    @property
    def output_marker(self) -> str:
        """Return the output commit marker key."""
        return f"{self.output_prefix}_SUCCESS.json"


class ArtifactDigest(BaseModel):
    """Canonical content identity for one immutable object."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    byte_length: int = Field(alias="byteLength", ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_payload(cls, key: str, payload: bytes) -> Self:
        """Build the digest contract for exact bytes."""
        return cls(
            key=key,
            byteLength=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )


class ArtifactMarker(BaseModel):
    """Marker-last commit record for a set of immutable objects."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["smurf-rgw-analysis/v1"] = Field(
        alias="schemaVersion",
    )
    run_id: RunId = Field(alias="runId")
    artifacts: tuple[ArtifactDigest, ...] = Field(min_length=1)

    @field_validator("artifacts")
    @classmethod
    def artifacts_are_unique(
        cls, value: tuple[ArtifactDigest, ...]
    ) -> tuple[ArtifactDigest, ...]:
        """Reject ambiguous duplicate artifact identities."""
        keys = tuple(artifact.key for artifact in value)
        if len(keys) != len(set(keys)):
            msg = "artifact keys must be unique"
            raise ValueError(msg)
        return tuple(sorted(value, key=lambda artifact: artifact.key))


class AnalysisResult(BaseModel):
    """Stable JSON result consumed by the static result viewer."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    row_count: int = Field(alias="rowCount", ge=1)
    amount_sum: Decimal = Field(alias="amountSum", ge=0, decimal_places=2)
    amount_average: Decimal = Field(alias="amountAverage", ge=0, decimal_places=2)


class RunIdInput(BaseModel):
    """Boundary wrapper that parses one path-safe run ID."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    value: RunId


def canonical_json(model: BaseModel) -> bytes:
    """Serialize a boundary model deterministically with one trailing newline."""
    payload = model.model_dump(mode="json", by_alias=True)
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def parse_run_id(value: str) -> RunId:
    """Parse an untrusted run ID into its path-safe semantic type."""
    return RunIdInput.model_validate({"value": value}).value
