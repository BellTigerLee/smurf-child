"""Canonical unsigned CI evidence generation."""

import hashlib
import re
import struct
from dataclasses import dataclass
from typing import Annotated, ClassVar, Final, Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_DUPLICATE_DIGEST_CODE: Final = "duplicate_image_digest"
_DUPLICATE_DIGEST_MESSAGE: Final = "image digests must be unique"
type AnnotatedDigest = str
type NonEmpty = Annotated[str, Field(min_length=1)]
type CanonicalRepository = Annotated[
    str, Field(pattern=r"^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")
]
type Digest = Annotated[str, Field(pattern=_DIGEST.pattern)]


class EvidenceInput(BaseModel):
    """Closed signed-domain evidence input."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        validate_by_name=True,
        validate_by_alias=False,
    )

    workflow_issuer: NonEmpty = Field(alias="workflowIssuer")
    workflow_subject: NonEmpty = Field(alias="workflowSubject")
    workflow_name: NonEmpty = Field(alias="workflowName")
    run_id: NonEmpty = Field(alias="runId")
    repository: CanonicalRepository
    path: Literal["deploy/dev"]
    sha: str = Field(alias="sourceSha", pattern=_SHA.pattern)
    build_passed: bool = Field(alias="buildPassed")
    tests_passed: bool = Field(alias="testsPassed")
    bundle_digest: Digest = Field(alias="bundleDigest")
    image_digests: tuple[Digest, ...] = Field(alias="imageDigests", min_length=1)
    started_at: str = Field(alias="startedAt", pattern=_TIME.pattern)
    completed_at: str = Field(alias="completedAt", pattern=_TIME.pattern)

    @field_validator("image_digests")
    @classmethod
    def unique_image_digests(cls, values: tuple[Digest, ...]) -> tuple[Digest, ...]:
        """Reject duplicate image identities from the signed payload."""
        if len(values) != len(set(values)):
            raise PydanticCustomError(_DUPLICATE_DIGEST_CODE, _DUPLICATE_DIGEST_MESSAGE)
        return values


@dataclass(frozen=True, slots=True)
class CanonicalEvidence:
    """Unsigned canonical payload, digest, and external signature input."""

    payload: bytes
    digest: str
    signature_input: bytes


def build_evidence(value: EvidenceInput) -> CanonicalEvidence:
    """Canonicalize payload and apply exact evidence/signature domains."""
    payload = rfc8785.dumps(value.model_dump(by_alias=True, mode="json"))
    length = struct.pack(">Q", len(payload))
    digest_input = b"SMURFX-EVIDENCE\0v1\0" + length + payload
    signature_input = b"SMURFX-EVIDENCE-SIGNATURE\0v1\0" + length + payload
    return CanonicalEvidence(
        payload,
        f"sha256:{hashlib.sha256(digest_input).hexdigest()}",
        signature_input,
    )
