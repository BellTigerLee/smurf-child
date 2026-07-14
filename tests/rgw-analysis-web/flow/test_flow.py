from pathlib import Path

import pytest
from smurf_flow.errors import (
    ArtifactCollisionError,
    ArtifactIntegrityError,
    PollTimeoutError,
    StorageError,
    WebAssetError,
)
from smurf_flow.flow import FlowRuntime, analyze_run, seed_run
from smurf_flow.render import WebAssets

from .fakes import FakePoller, FakeStore, runtime


def test_seed_is_idempotent_when_exact_run_already_exists() -> None:
    # Given: an empty immutable object store
    store = FakeStore()
    flow = runtime(store)

    # When: the same run is seeded twice
    first = seed_run(flow)
    second = seed_run(flow)

    # Then: bytes and marker identity remain unchanged
    assert first == second
    assert set(store.objects) == {flow.paths.dataset, flow.paths.input_marker}
    assert tuple(store.objects) == (flow.paths.dataset, flow.paths.input_marker)


def test_seed_fails_closed_when_marker_exists_without_data() -> None:
    # Given: a committed marker whose data object was removed
    store = FakeStore()
    flow = runtime(store)
    _ = seed_run(flow)
    del store.objects[flow.paths.dataset]

    # When/Then: reseeding reports corruption instead of repairing it
    with pytest.raises(ArtifactIntegrityError):
        _ = seed_run(flow)
    assert flow.paths.dataset not in store.objects


def test_seed_preserves_existing_bytes_when_collision_occurs() -> None:
    # Given: an uncommitted object at the canonical dataset key
    store = FakeStore()
    flow = runtime(store)
    store.objects[flow.paths.dataset] = b"different"

    # When/Then: create-only publication rejects and preserves it
    with pytest.raises(ArtifactCollisionError):
        _ = seed_run(flow)
    assert store.objects[flow.paths.dataset] == b"different"
    assert flow.paths.input_marker not in store.objects


def test_analyze_ignores_stale_and_duplicate_list_entries_deterministically() -> None:
    # Given: one committed CSV plus stale and duplicate listing entries
    store = FakeStore()
    flow = runtime(store)
    _ = seed_run(flow)
    stale = f"{flow.paths.input_prefix}stale.csv"
    store.objects[stale] = b"record_id,label,amount\n99,stale,999.00\n"
    store.listed = (stale, flow.paths.dataset, flow.paths.dataset)

    # When: analysis resolves the committed CSV set
    marker = analyze_run(flow)

    # Then: only the marker-authorized input contributes to exact output
    assert marker.run_id == flow.paths.run_id
    assert store.objects[flow.paths.result] == (
        b'{"amountAverage":"30.00","amountSum":"150.00","rowCount":5}\n'
    )
    assert b"stale.csv" not in store.objects[flow.paths.index]
    assert b'class="report"' in store.objects[flow.paths.index]
    assert b"<style>\n:root" in store.objects[flow.paths.index]
    assert tuple(store.objects)[-1] == flow.paths.output_marker


def test_analyze_writes_no_output_when_web_asset_is_missing(tmp_path: Path) -> None:
    # Given: committed input and an empty configured viewer asset directory
    store = FakeStore()
    valid = runtime(store)
    _ = seed_run(valid)
    missing_assets = FlowRuntime(
        store=valid.store,
        paths=valid.paths,
        wait=valid.wait,
        poller=valid.poller,
        web_assets=WebAssets(directory=tmp_path),
    )

    # When/Then: analysis fails closed before any output object is published
    with pytest.raises(WebAssetError):
        _ = analyze_run(missing_assets)
    assert not any(key.startswith(valid.paths.output_prefix) for key in store.objects)


def test_analyze_writes_no_marker_when_storage_fails() -> None:
    # Given: valid input and a result write failure
    store = FakeStore()
    flow = runtime(store)
    _ = seed_run(flow)
    store.fail_create_key = flow.paths.result

    # When/Then: the typed storage error leaves output uncommitted
    with pytest.raises(StorageError):
        _ = analyze_run(flow)
    assert flow.paths.output_marker not in store.objects


def test_analyze_times_out_without_wall_clock_sleep() -> None:
    # Given: no input marker and an injected monotonic poller
    store = FakeStore()
    poller = FakePoller()
    flow = runtime(store, poller=poller)

    # When/Then: polling stops exactly at the bounded deadline
    with pytest.raises(PollTimeoutError):
        _ = analyze_run(flow)
    assert poller.elapsed == 2
    assert flow.paths.result not in store.objects
