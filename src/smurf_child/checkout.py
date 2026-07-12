"""Exact clean Git checkout proof."""

import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from smurf_child.models import ContractErrorCategory, ContractValidationError

_CANONICAL_URL = re.compile(r"^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class CheckoutExpectation:
    """Exact source tuple expected from the CI evidence boundary."""

    repository: str
    sha: str
    path: str


@dataclass(frozen=True, slots=True)
class ExactCheckout:
    """Verified immutable source identity and manifest paths."""

    repository: str
    head_sha: str
    manifest_paths: tuple[str, ...]


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed Git executable, typed arguments
            ["/usr/bin/git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ContractValidationError(
            ContractErrorCategory.EXACT_CHECKOUT, root
        ) from error
    return completed.stdout.strip()


def read_head(root: Path) -> str:
    """Read the full checked-out HEAD through the bounded Git adapter."""
    return _git(root, "rev-parse", "HEAD")


def verify_checkout(root: Path, expected: CheckoutExpectation) -> ExactCheckout:
    """Require canonical origin, exact HEAD, clean tree, and regular YAML files."""
    normalized_root = root.resolve(strict=True)
    path = PurePosixPath(expected.path)
    if (
        _CANONICAL_URL.fullmatch(expected.repository) is None
        or _FULL_SHA.fullmatch(expected.sha) is None
        or path.as_posix() != expected.path
        or path.is_absolute()
        or ".." in path.parts
        or path.parts != ("deploy", "dev")
    ):
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, root)
    if Path(_git(normalized_root, "rev-parse", "--show-toplevel")) != normalized_root:
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, root)
    if _git(normalized_root, "remote", "get-url", "origin") != expected.repository:
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, root)
    head = _git(normalized_root, "rev-parse", "HEAD")
    if head != expected.sha or _git(
        normalized_root, "status", "--porcelain", "--untracked-files=all"
    ):
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, root)
    if (
        _git(normalized_root, "ls-files", "--stage", "--", expected.path).find(
            "160000 "
        )
        >= 0
    ):
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, root)
    deploy = normalized_root.joinpath(*path.parts)
    manifests: list[str] = []
    for candidate in deploy.iterdir():
        relative = candidate.relative_to(normalized_root).as_posix()
        mode = candidate.lstat().st_mode
        if (
            candidate.suffix != ".yaml"
            or not stat.S_ISREG(mode)
            or candidate.resolve().parent != deploy
        ):
            raise ContractValidationError(
                ContractErrorCategory.EXACT_CHECKOUT, candidate
            )
        manifests.append(relative)
    if not manifests:
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, deploy)
    tracked = tuple(
        line
        for line in _git(
            normalized_root, "ls-files", "--", "deploy/dev/*.yaml"
        ).splitlines()
        if line
    )
    filesystem = tuple(sorted(manifests, key=lambda value: value.encode()))
    if filesystem != tuple(sorted(tracked, key=lambda value: value.encode())):
        raise ContractValidationError(ContractErrorCategory.EXACT_CHECKOUT, deploy)
    return ExactCheckout(
        expected.repository,
        head,
        filesystem,
    )
