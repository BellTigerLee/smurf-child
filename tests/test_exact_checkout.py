import subprocess
from pathlib import Path
from typing import Literal, assert_never

import pytest

from smurf_child.checkout import CheckoutExpectation, verify_checkout
from smurf_child.models import ContractErrorCategory, ContractValidationError

CANONICAL_ORIGIN = "git@github.com:BellTigerLee/smurf-child.git"
type CheckoutMutation = Literal["dirty", "remote", "sha", "symlink", "traversal"]


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed Git executable in test fixture
        ["/usr/bin/git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "child"
    root.mkdir(parents=True)
    _ = _git(root, "init", "-q")
    _ = _git(root, "config", "user.email", "test@example.com")
    _ = _git(root, "config", "user.name", "Contract Test")
    _ = _git(root, "remote", "add", "origin", CANONICAL_ORIGIN)
    deploy = root / "deploy" / "dev"
    deploy.mkdir(parents=True)
    _ = (deploy / "configmap.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata: {name: sample}\n",
        encoding="utf-8",
    )
    _ = _git(root, "add", ".")
    _ = _git(root, "commit", "-qm", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


def _expectation(sha: str) -> CheckoutExpectation:
    return CheckoutExpectation(CANONICAL_ORIGIN, sha, "deploy/dev")


def test_exact_checkout_accepts_clean_regular_bundle(tmp_path: Path) -> None:
    # Given: a clean repository at an exact full SHA and canonical origin.
    root, sha = _repository(tmp_path)

    # When: exact checkout proof is derived.
    checkout = verify_checkout(root, _expectation(sha))

    # Then: only the normalized regular manifest path is admitted.
    assert checkout.head_sha == sha
    assert checkout.manifest_paths == ("deploy/dev/configmap.yaml",)


@pytest.mark.parametrize("mutation", ["dirty", "remote", "sha", "symlink", "traversal"])
def test_exact_checkout_rejects_mutation(
    mutation: CheckoutMutation, tmp_path: Path
) -> None:
    # Given: one exact-checkout invariant is violated.
    root, sha = _repository(tmp_path)
    expectation = _expectation(sha)
    match mutation:
        case "dirty":
            _ = (root / "dirty.txt").write_text("dirty", encoding="utf-8")
        case "remote":
            _ = _git(
                root,
                "remote",
                "set-url",
                "origin",
                "https://github.com/BellTigerLee/smurf-child.git",
            )
        case "sha":
            expectation = _expectation("a" * 40)
        case "symlink":
            (root / "deploy" / "dev" / "link.yaml").symlink_to("configmap.yaml")
        case "traversal":
            expectation = CheckoutExpectation(CANONICAL_ORIGIN, sha, "deploy/../dev")
        case _ as unreachable:
            assert_never(unreachable)

    # When: checkout proof is attempted.
    with pytest.raises(ContractValidationError) as caught:
        _ = verify_checkout(root, expectation)

    # Then: the violation has the checkout category and no partial proof.
    assert caught.value.category is ContractErrorCategory.EXACT_CHECKOUT


def test_exact_checkout_rejects_submodule(tmp_path: Path) -> None:
    # Given: deploy/dev contains a committed Git submodule.
    root, _ = _repository(tmp_path)
    module, _ = _repository(tmp_path / "module-parent")
    _ = _git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(module),
        "deploy/dev/module",
    )
    _ = _git(root, "commit", "-qam", "submodule")
    sha = _git(root, "rev-parse", "HEAD")

    # When: checkout proof is attempted.
    with pytest.raises(ContractValidationError) as caught:
        _ = verify_checkout(root, _expectation(sha))

    # Then: submodules are excluded from the plain-file bundle.
    assert caught.value.category is ContractErrorCategory.EXACT_CHECKOUT
