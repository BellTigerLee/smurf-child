from pathlib import Path

import pytest

from smurf_child import contract
from smurf_child.models import ChildRequest, ManifestInventory


def _accept_all_request(_path: Path) -> None:
    return None


def _accept_all_manifests(_path: Path) -> None:
    return None


def _assert_request_contract(path: Path) -> None:
    result = contract.parse_request(path)
    assert isinstance(result, ChildRequest), "expected typed ChildRequest"
    assert result.workload_id == "sample-api"
    assert result.target == "both"


def _assert_manifest_contract(path: Path) -> None:
    result = contract.validate_manifests(path)
    assert isinstance(result, ManifestInventory), "expected typed ManifestInventory"
    assert result.kinds == ("ConfigMap", "Deployment", "Service")
    assert result.namespace_neutral is True


def test_request_assertions_reject_accept_all_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a deliberately wrong request parser that accepts everything as None.
    monkeypatch.setattr(contract, "parse_request", _accept_all_request)

    # When: the real contract assertions inspect its result.
    with pytest.raises(AssertionError, match="typed ChildRequest"):
        _assert_request_contract(Path("smurfx/request.yaml"))

    # Then: accept-all cannot satisfy the future request contract.


def test_manifest_assertions_reject_accept_all_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a deliberately wrong manifest validator that accepts everything as None.
    monkeypatch.setattr(contract, "validate_manifests", _accept_all_manifests)

    # When: the real contract assertions inspect its result.
    with pytest.raises(AssertionError, match="typed ManifestInventory"):
        _assert_manifest_contract(Path("deploy/dev"))

    # Then: accept-all cannot satisfy the future manifest contract.
