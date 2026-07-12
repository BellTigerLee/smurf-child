from pathlib import Path

from smurf_child.contract import parse_request, validate_manifests


def test_namespace_reaches_forbidden_kind_rejection() -> None:
    # Given: a well-formed Namespace fixture.
    fixture_path = Path("tests/fixtures/adversarial/namespace.yaml")

    # When: the manifest boundary validates that fixture.
    validate_manifests(fixture_path, behavior="forbidden_kind")

    # Then: RED records the intended rejection category.


def test_mutable_image_reaches_immutable_image_rejection() -> None:
    # Given: a well-formed Deployment with a mutable image tag.
    fixture_path = Path("tests/fixtures/adversarial/mutable-image.yaml")

    # When: the manifest boundary validates that fixture.
    validate_manifests(fixture_path, behavior="immutable_image")

    # Then: RED records the intended rejection category.


def test_karmada_policy_reaches_forbidden_kind_rejection() -> None:
    # Given: a well-formed Karmada PropagationPolicy fixture.
    fixture_path = Path("tests/fixtures/adversarial/karmada-policy.yaml")

    # When: the manifest boundary validates that fixture.
    validate_manifests(fixture_path, behavior="forbidden_kind")

    # Then: RED records the intended rejection category.


def test_effective_policy_request_reaches_named_rejection() -> None:
    # Given: a well-formed request that improperly owns effective policy.
    request_path = Path("tests/fixtures/adversarial/effective-policy-request.yaml")

    # When: the request boundary parses that fixture.
    parse_request(request_path, behavior="effective_policy")

    # Then: RED records the intended rejection category.
