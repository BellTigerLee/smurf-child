"""Typed flow failures safe for CLI reporting."""

from dataclasses import dataclass
from typing import override


class FlowError(Exception):
    """Base class for expected flow failures."""


@dataclass(frozen=True, slots=True)
class StorageError(FlowError):
    """An object-store operation failed."""

    operation: str
    key: str
    code: str

    @override
    def __str__(self) -> str:
        """Return the redacted operation, key, and SDK code."""
        return f"storage {self.operation} failed for {self.key!r} ({self.code})"


@dataclass(frozen=True, slots=True)
class ArtifactCollisionError(FlowError):
    """An immutable artifact key already contains different bytes."""

    key: str

    @override
    def __str__(self) -> str:
        """Return the colliding public object key."""
        return f"immutable artifact collision at {self.key!r}"


@dataclass(frozen=True, slots=True)
class ArtifactIntegrityError(FlowError):
    """A marker and its artifact do not agree."""

    key: str
    reason: str

    @override
    def __str__(self) -> str:
        """Return the object key and integrity class."""
        return f"artifact integrity failure for {self.key!r}: {self.reason}"


@dataclass(frozen=True, slots=True)
class InputDataError(FlowError):
    """A CSV input violates the analysis contract."""

    key: str
    reason: str

    @override
    def __str__(self) -> str:
        """Return the input key and validation class."""
        return f"invalid CSV input {self.key!r}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PollTimeoutError(FlowError):
    """A bounded marker wait expired."""

    key: str
    timeout_seconds: float

    @override
    def __str__(self) -> str:
        """Return the bounded wait deadline and marker key."""
        return f"timed out after {self.timeout_seconds:g}s waiting for {self.key!r}"


@dataclass(frozen=True, slots=True)
class LocalPublishError(FlowError):
    """An atomic local artifact publication failed."""

    path: str
    reason: str

    @override
    def __str__(self) -> str:
        """Return the target path and local failure class."""
        return f"local publication failed for {self.path!r}: {self.reason}"


@dataclass(frozen=True, slots=True)
class WebAssetError(FlowError):
    """A required static viewer asset is absent or malformed."""

    path: str
    reason: str

    @override
    def __str__(self) -> str:
        """Return the asset path and validation class without asset content."""
        return f"web asset failure for {self.path!r}: {self.reason}"
