"""Frozen request boundary models reserved for Task 4."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

type DeveloperId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type ChildId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type WorkloadId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
type EnvironmentId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,31}$")]
type Target = Literal["b", "c", "both"]


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
