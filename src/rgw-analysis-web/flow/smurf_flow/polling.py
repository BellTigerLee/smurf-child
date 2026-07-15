"""Injectable bounded marker polling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from smurf_flow.errors import PollTimeoutError
from smurf_flow.protocol import parse_marker

if TYPE_CHECKING:
    from smurf_flow.models import ArtifactMarker
    from smurf_flow.storage import ObjectStore


class Poller(Protocol):
    """Clock and sleeper capability for deterministic wait tests."""

    def monotonic(self) -> float:
        """Return monotonic seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Advance or sleep for bounded seconds."""
        ...


class SystemPoller:
    """Production monotonic clock and sleeper."""

    def monotonic(self) -> float:
        """Return system monotonic seconds."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Sleep without depending on wall-clock time."""
        time.sleep(seconds)


@dataclass(frozen=True, slots=True)
class MarkerWait:
    """Bounded wait parameters for one marker key."""

    key: str
    timeout_seconds: float
    interval_seconds: float


def wait_for_marker(
    store: ObjectStore,
    request: MarkerWait,
    poller: Poller,
) -> ArtifactMarker:
    """Poll until a marker exists or the monotonic deadline expires."""
    started = poller.monotonic()
    while True:
        payload = store.read(request.key)
        if payload is not None:
            return parse_marker(request.key, payload)
        elapsed = poller.monotonic() - started
        if elapsed >= request.timeout_seconds:
            raise PollTimeoutError(
                key=request.key,
                timeout_seconds=request.timeout_seconds,
            )
        poller.sleep(min(request.interval_seconds, request.timeout_seconds - elapsed))
