"""Seed, analyze, and result-sync use cases."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from smurf_flow.dataset import DATASET_BYTES, analyze_rows, parse_csv
from smurf_flow.errors import ArtifactIntegrityError, InputDataError, LocalPublishError
from smurf_flow.models import ArtifactMarker, RunPaths, canonical_json
from smurf_flow.polling import MarkerWait, Poller, wait_for_marker
from smurf_flow.protocol import (
    ArtifactPayload,
    Publication,
    publish_artifacts,
    verify_marker,
)
from smurf_flow.render import ReportValues, WebAssets, render_result_html

if TYPE_CHECKING:
    from smurf_flow.storage import ObjectStore


@dataclass(frozen=True, slots=True)
class FlowRuntime:
    """Capabilities and immutable configuration for one run."""

    store: ObjectStore
    paths: RunPaths
    wait: MarkerWait
    poller: Poller
    web_assets: WebAssets


@dataclass(frozen=True, slots=True)
class ViewerPair:
    """Exact result and index bytes for one viewer generation."""

    result: bytes
    index: bytes


def seed_run(runtime: FlowRuntime) -> ArtifactMarker:
    """Publish the canonical five-row dataset and its marker last."""
    dataset = ArtifactPayload(
        key=runtime.paths.dataset,
        payload=DATASET_BYTES,
        content_type="text/csv",
    )
    return publish_artifacts(
        runtime.store,
        Publication(
            marker_key=runtime.paths.input_marker,
            run_id=runtime.paths.run_id,
            artifacts=(dataset,),
        ),
    )


def analyze_run(runtime: FlowRuntime) -> ArtifactMarker:
    """Verify deterministic CSV inputs and publish both viewer artifacts."""
    marker = wait_for_marker(runtime.store, runtime.wait, runtime.poller)
    _require_run(marker, runtime)
    verified = verify_marker(runtime.store, runtime.paths.input_marker, marker)
    listed = set(runtime.store.list_keys(runtime.paths.input_prefix))
    csv_artifacts = tuple(
        sorted(
            (
                artifact
                for artifact in verified
                if artifact.key.endswith(".csv") and artifact.key in listed
            ),
            key=lambda artifact: artifact.key,
        ),
    )
    if not csv_artifacts:
        raise ArtifactIntegrityError(
            key=runtime.paths.input_marker,
            reason="marker commits no listed CSV inputs",
        )
    rows = tuple(
        row
        for artifact in csv_artifacts
        for row in parse_csv(artifact.key, artifact.payload)
    )
    identifiers = tuple(row.record_id for row in rows)
    if len(identifiers) != len(set(identifiers)):
        raise InputDataError(
            key=runtime.paths.input_prefix, reason="duplicate record_id"
        )
    result = analyze_rows(rows)
    source_keys = tuple(artifact.key for artifact in csv_artifacts)
    result_payload = canonical_json(result)
    index_payload = render_result_html(
        runtime.web_assets,
        ReportValues.from_result(runtime.paths.run_id, result, source_keys),
    )
    return publish_artifacts(
        runtime.store,
        Publication(
            marker_key=runtime.paths.output_marker,
            run_id=runtime.paths.run_id,
            artifacts=(
                ArtifactPayload(
                    key=runtime.paths.result,
                    payload=result_payload,
                    content_type="application/json",
                ),
                ArtifactPayload(
                    key=runtime.paths.index,
                    payload=index_payload,
                    content_type="text/html",
                ),
            ),
        ),
    )


def fetch_run(runtime: FlowRuntime, output_directory: Path) -> tuple[Path, Path]:
    """Poll, verify, and atomically publish result files for the web sidecar."""
    marker = wait_for_marker(runtime.store, runtime.wait, runtime.poller)
    _require_run(marker, runtime)
    artifacts = verify_marker(runtime.store, runtime.paths.output_marker, marker)
    by_key = {artifact.key: artifact.payload for artifact in artifacts}
    try:
        result_payload = by_key[runtime.paths.result]
        index_payload = by_key[runtime.paths.index]
    except KeyError as error:
        raise ArtifactIntegrityError(
            key=runtime.paths.output_marker,
            reason="required viewer artifact is absent",
        ) from error
    return publish_viewer_generation(
        output_directory,
        marker,
        ViewerPair(result=result_payload, index=index_payload),
    )


def _require_run(marker: ArtifactMarker, runtime: FlowRuntime) -> None:
    if marker.run_id != runtime.paths.run_id:
        raise ArtifactIntegrityError(
            key=runtime.wait.key,
            reason="marker run ID mismatch",
        )


def publish_viewer_generation(
    output_directory: Path,
    marker: ArtifactMarker,
    pair: ViewerPair,
) -> tuple[Path, Path]:
    """Publish a complete pair behind one atomically replaced symlink."""
    generation_id = hashlib.sha256(canonical_json(marker)).hexdigest()
    generations = output_directory / ".generations"
    generation = generations / generation_id
    current = output_directory / "current"
    staging: Path | None = None
    temporary_link: Path | None = None
    try:
        generations.mkdir(parents=True, exist_ok=True)
        if generation.exists():
            if (generation / "result.json").read_bytes() != pair.result or (
                generation / "index.html"
            ).read_bytes() != pair.index:
                raise LocalPublishError(
                    path=str(generation),
                    reason="generation-collision",
                )
        else:
            staging = Path(
                tempfile.mkdtemp(
                    dir=generations,
                    prefix=f".{generation_id}.",
                    suffix=".tmp",
                ),
            )
            _ = (staging / "result.json").write_bytes(pair.result)
            _ = (staging / "index.html").write_bytes(pair.index)
            _ = staging.replace(generation)
            staging = None
        temporary_link = output_directory / f".current.{uuid.uuid4().hex}.tmp"
        temporary_link.symlink_to(
            Path(".generations") / generation_id,
            target_is_directory=True,
        )
        _ = temporary_link.replace(current)
    except OSError as error:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if temporary_link is not None:
            temporary_link.unlink(missing_ok=True)
        raise LocalPublishError(
            path=str(output_directory),
            reason=type(error).__name__,
        ) from error
    return current / "result.json", current / "index.html"
