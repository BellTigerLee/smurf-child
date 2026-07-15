from collections.abc import Callable
from pathlib import Path
from typing import Final

from smurf_flow.errors import StorageError
from smurf_flow.flow import FlowRuntime
from smurf_flow.models import RunPaths, parse_run_id
from smurf_flow.polling import MarkerWait
from smurf_flow.render import WebAssets
from smurf_flow.storage import Created, CreateResult, Existing

WEB_ASSETS: Final = Path(__file__).parents[3] / "src" / "rgw-analysis-web" / "web"


class FakeStore:
    """Mutable in-memory object store used to test the immutable protocol."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.listed: tuple[str, ...] | None = None
        self.fail_create_key: str | None = None

    def read(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def create(self, key: str, payload: bytes, content_type: str) -> CreateResult:
        del content_type
        if key == self.fail_create_key:
            raise StorageError(operation="create", key=key, code="injected")
        existing = self.objects.get(key)
        if existing is not None:
            return Existing(payload=existing)
        self.objects[key] = payload
        return Created()

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        if self.listed is not None:
            return self.listed
        return tuple(sorted(key for key in self.objects if key.startswith(prefix)))


class FakePoller:
    """Mutable monotonic test clock with an optional delayed action."""

    def __init__(self, delayed_action: Callable[[], None] | None = None) -> None:
        self.elapsed: float = 0.0
        self.delayed_action: Callable[[], None] | None = delayed_action

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds
        action = self.delayed_action
        if action is not None:
            self.delayed_action = None
            action()


def runtime(
    store: FakeStore,
    marker_kind: str = "input",
    poller: FakePoller | None = None,
) -> FlowRuntime:
    paths = RunPaths(run_id=parse_run_id("run-1"))
    marker = paths.input_marker if marker_kind == "input" else paths.output_marker
    return FlowRuntime(
        store=store,
        paths=paths,
        wait=MarkerWait(key=marker, timeout_seconds=2, interval_seconds=1),
        poller=poller or FakePoller(),
        web_assets=WebAssets(directory=WEB_ASSETS),
    )
