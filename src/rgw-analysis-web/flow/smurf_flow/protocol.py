"""Marker-last immutable artifact publication protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from smurf_flow.errors import ArtifactCollisionError, ArtifactIntegrityError
from smurf_flow.models import (
    SCHEMA_VERSION,
    ArtifactDigest,
    ArtifactMarker,
    RunId,
    canonical_json,
)

if TYPE_CHECKING:
    from smurf_flow.storage import ObjectStore


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    """Exact bytes and media type for one immutable artifact."""

    key: str
    payload: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class Publication:
    """Marker identity and exact payloads for one atomic publication."""

    marker_key: str
    run_id: RunId
    artifacts: tuple[ArtifactPayload, ...]


def parse_marker(key: str, payload: bytes) -> ArtifactMarker:
    """Parse marker bytes once at the object-store trust boundary."""
    try:
        return ArtifactMarker.model_validate_json(payload)
    except ValidationError as error:
        raise ArtifactIntegrityError(key=key, reason="malformed marker") from error


def verify_marker(
    store: ObjectStore,
    marker_key: str,
    marker: ArtifactMarker,
) -> tuple[ArtifactPayload, ...]:
    """Read and verify every artifact committed by a marker."""
    verified: list[ArtifactPayload] = []
    for digest in marker.artifacts:
        payload = store.read(digest.key)
        if payload is None:
            raise ArtifactIntegrityError(key=digest.key, reason="object is missing")
        actual = ArtifactDigest.from_payload(digest.key, payload)
        if actual != digest:
            raise ArtifactIntegrityError(
                key=digest.key, reason="checksum or length mismatch"
            )
        verified.append(
            ArtifactPayload(
                key=digest.key,
                payload=payload,
                content_type="application/octet-stream",
            ),
        )
    if not verified:
        raise ArtifactIntegrityError(key=marker_key, reason="marker is empty")
    return tuple(verified)


def publish_artifacts(
    store: ObjectStore,
    publication: Publication,
) -> ArtifactMarker:
    """Publish artifacts create-only and commit their marker last."""
    marker = ArtifactMarker(
        schemaVersion=SCHEMA_VERSION,
        runId=publication.run_id,
        artifacts=tuple(
            ArtifactDigest.from_payload(artifact.key, artifact.payload)
            for artifact in publication.artifacts
        ),
    )
    marker_payload = canonical_json(marker)
    existing_marker = store.read(publication.marker_key)
    if existing_marker is not None:
        parsed = parse_marker(publication.marker_key, existing_marker)
        if canonical_json(parsed) != marker_payload:
            raise ArtifactCollisionError(key=publication.marker_key)
        _ = verify_marker(store, publication.marker_key, parsed)
        return parsed

    for artifact in publication.artifacts:
        result = store.create(
            artifact.key,
            artifact.payload,
            artifact.content_type,
        )
        if not result.matches(artifact.payload):
            raise ArtifactCollisionError(key=artifact.key)

    marker_result = store.create(
        publication.marker_key,
        marker_payload,
        "application/json",
    )
    if not marker_result.matches(marker_payload):
        raise ArtifactCollisionError(key=publication.marker_key)
    return marker
