"""Canonical unsigned CI evidence generation."""

import hashlib
import re
import struct
from dataclasses import dataclass
from typing import ClassVar, Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
type AnnotatedDigest = str


class EvidenceInput(BaseModel):
    """Closed signed-domain evidence input."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    workflow_issuer: str
    workflow_subject: str
    workflow_name: str
    run_id: str
    repository: str
    path: Literal["deploy/dev"]
    sha: str = Field(pattern=_SHA.pattern)
    build_result: Literal["success", "failure"]
    test_result: Literal["success", "failure"]
    bundle_digest: str = Field(pattern=_DIGEST.pattern)
    image_digests: tuple[AnnotatedDigest, ...]
    started_at: str = Field(pattern=_TIME.pattern)
    completed_at: str = Field(pattern=_TIME.pattern)


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
