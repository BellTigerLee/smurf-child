from pathlib import Path

import pytest

from smurf_child.contract import parse_request
from smurf_child.models import (
    ChildRequest,
    ContractErrorCategory,
    ContractValidationError,
)


def test_request_parses_inert_identity_and_both_target() -> None:
    # Given: the repository's inert request file.
    request_path = Path("smurfx/request.yaml")

    # When: the request is parsed.
    request = parse_request(request_path)

    # Then: stable identities and the literal target are typed values.
    assert request == ChildRequest(
        apiVersion="smurfx.dev/v1alpha1",
        kind="ChildRequest",
        developerId="developer-belltigerlee",
        childId="smurf-child",
        workloadId="sample-api",
        environment="dev",
        target="both",
    )


@pytest.mark.parametrize("target", ["b", "c", "both"])
def test_request_parses_each_literal_target(target: str, tmp_path: Path) -> None:
    # Given: a valid request containing one literal target.
    request_path = tmp_path / "request.yaml"
    _ = request_path.write_text(
        f"""apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-belltigerlee
childId: smurf-child
workloadId: sample-api
environment: dev
target: {target}
""",
        encoding="utf-8",
    )

    # When: the request is parsed.
    request = parse_request(request_path)

    # Then: the target remains the exact requested literal.
    assert request.target == target


def test_request_rejects_nonexistent_file(tmp_path: Path) -> None:
    # Given: a request path that does not exist.
    request_path = tmp_path / "missing.yaml"

    # When: the request is parsed.
    with pytest.raises(ContractValidationError) as caught:
        _ = parse_request(request_path)

    # Then: absence has its own typed category.
    assert caught.value.category is ContractErrorCategory.REQUEST_NOT_FOUND


def test_request_rejects_malformed_yaml() -> None:
    # Given: a malformed YAML request fixture.
    request_path = Path("tests/fixtures/adversarial/malformed-request.yaml")

    # When: the request is parsed.
    with pytest.raises(ContractValidationError) as caught:
        _ = parse_request(request_path)

    # Then: syntax failure is distinct from absence and schema failure.
    assert caught.value.category is ContractErrorCategory.REQUEST_MALFORMED


def test_request_rejects_invalid_schema() -> None:
    # Given: valid YAML with an unsupported target literal.
    request_path = Path("tests/fixtures/adversarial/invalid-request.yaml")

    # When: the request is parsed.
    with pytest.raises(ContractValidationError) as caught:
        _ = parse_request(request_path)

    # Then: typed schema rejection is reported.
    assert caught.value.category is ContractErrorCategory.REQUEST_SCHEMA


def test_request_rejects_child_owned_effective_policy() -> None:
    # Given: a request that improperly embeds effective policy.
    request_path = Path("tests/fixtures/adversarial/effective-policy-request.yaml")

    # When: the request is parsed.
    with pytest.raises(ContractValidationError) as caught:
        _ = parse_request(request_path)

    # Then: child-owned effective policy has an exact category.
    assert caught.value.category is ContractErrorCategory.EFFECTIVE_POLICY
