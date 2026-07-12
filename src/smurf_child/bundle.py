"""Exact canonical child bundle framing."""

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import rfc8785

from smurf_child.manifest import parse_manifest


@dataclass(frozen=True, slots=True)
class CanonicalBundle:
    """Canonical framed bytes plus their admitted inventory."""

    bytes: bytes
    digest: str
    kinds: tuple[str, ...]
    images: tuple[str, ...]


def build_bundle(root: Path, paths: tuple[str, ...]) -> CanonicalBundle:
    """Frame sorted repository-relative paths and RFC 8785 documents."""
    framed = bytearray(b"SMURFX-BUNDLE\0v1\0")
    ordered = tuple(sorted(paths, key=lambda path: path.encode("utf-8")))
    framed.extend(struct.pack(">I", len(ordered)))
    kinds: list[str] = []
    images: list[str] = []
    for relative in ordered:
        normalized = PurePosixPath(relative)
        path_bytes = normalized.as_posix().encode("utf-8")
        resource, value, resource_images = parse_manifest(root / normalized)
        document = rfc8785.dumps(value)
        framed.extend(struct.pack(">I", len(path_bytes)))
        framed.extend(path_bytes)
        framed.extend(struct.pack(">Q", len(document)))
        framed.extend(document)
        kinds.append(resource.kind)
        images.extend(resource_images)
    bundle_bytes = bytes(framed)
    return CanonicalBundle(
        bundle_bytes,
        f"sha256:{hashlib.sha256(bundle_bytes).hexdigest()}",
        tuple(sorted(kinds)),
        tuple(sorted(images)),
    )
