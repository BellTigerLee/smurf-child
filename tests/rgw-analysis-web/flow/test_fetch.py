from pathlib import Path

import pytest
from smurf_flow.errors import ArtifactIntegrityError, LocalPublishError
from smurf_flow.flow import analyze_run, fetch_run, seed_run

from .fakes import FakePoller, FakeStore, runtime


def test_fetch_polls_then_publishes_and_cleans_temporaries(tmp_path: Path) -> None:
    # Given: output appears after the first result-sync poll
    store = FakeStore()
    producer = runtime(store)
    _ = seed_run(producer)

    def publish_output() -> None:
        _ = analyze_run(producer)

    poller = FakePoller(delayed_action=publish_output)
    consumer = runtime(store, marker_kind="output", poller=poller)

    # When: the sidecar fetches verified viewer artifacts
    result_path, index_path = fetch_run(consumer, tmp_path)

    # Then: complete files are visible and no generated temp remains
    assert result_path.read_bytes() == store.objects[consumer.paths.result]
    assert index_path.read_bytes() == store.objects[consumer.paths.index]
    assert result_path == tmp_path / "current" / "result.json"
    assert index_path == tmp_path / "current" / "index.html"
    assert (tmp_path / "current").is_symlink()
    assert tuple(tmp_path.rglob("*.tmp")) == ()


def test_fetch_preserves_existing_result_when_marker_is_corrupt(tmp_path: Path) -> None:
    # Given: a complete local result and a corrupt remote marker
    store = FakeStore()
    flow = runtime(store, marker_kind="output")
    existing = tmp_path / "result.json"
    _ = existing.write_bytes(b"preserve-me")
    store.objects[flow.paths.output_marker] = b"not-json"

    # When/Then: verification fails before local publication
    with pytest.raises(ArtifactIntegrityError):
        _ = fetch_run(flow, tmp_path)
    assert existing.read_bytes() == b"preserve-me"
    assert tuple(tmp_path.glob(".*.tmp")) == ()


def test_generation_publish_cleans_staging_when_first_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: verified outputs and a failure before a generation becomes visible
    store = FakeStore()
    producer = runtime(store)
    _ = seed_run(producer)
    _ = analyze_run(producer)
    consumer = runtime(store, marker_kind="output")

    def fail_replace(path: Path, replacement: Path) -> Path:
        del path, replacement
        raise OSError

    monkeypatch.setattr(Path, "replace", fail_replace)

    # When/Then: publication fails typed and removes its private staging directory
    with pytest.raises(LocalPublishError):
        _ = fetch_run(consumer, tmp_path)
    assert (tmp_path / "current").exists() is False
    assert tuple(tmp_path.rglob("*.tmp")) == ()


def test_fetch_restores_previous_pair_when_second_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a previous complete pair and a failure on the second file replacement
    store = FakeStore()
    producer = runtime(store)
    _ = seed_run(producer)
    _ = analyze_run(producer)
    consumer = runtime(store, marker_kind="output")
    previous = tmp_path / ".generations" / "previous"
    previous.mkdir(parents=True)
    result_path = tmp_path / "current" / "result.json"
    index_path = tmp_path / "current" / "index.html"
    _ = (tmp_path / "current").symlink_to(
        Path(".generations") / "previous",
        target_is_directory=True,
    )
    _ = (previous / "result.json").write_bytes(b"old-result")
    _ = (previous / "index.html").write_bytes(b"old-index")
    original_replace = Path.replace
    replacement_count = 0

    def fail_second_replace(path: Path, replacement: Path) -> Path:
        nonlocal replacement_count
        replacement_count += 1
        if replacement_count == 2:
            raise OSError
        return original_replace(path, replacement)

    monkeypatch.setattr(Path, "replace", fail_second_replace)

    # When: result sync attempts to publish the new verified pair
    with pytest.raises(LocalPublishError):
        _ = fetch_run(consumer, tmp_path)

    # Then: readers retain the complete previous generation and no temp survives
    assert result_path.read_bytes() == b"old-result"
    assert index_path.read_bytes() == b"old-index"
    assert replacement_count == 2
    assert tuple(tmp_path.rglob("*.tmp")) == ()
