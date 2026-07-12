from pathlib import Path

import pytest

from smurf_child.contract import validate_manifests
from smurf_child.models import ContractErrorCategory, ContractValidationError


def test_dev_bundle_returns_namespace_neutral_digest_inventory() -> None:
    # Given: the repository's plain development bundle.
    deploy_root = Path("deploy/dev")

    # When: the manifest bundle is validated.
    inventory = validate_manifests(deploy_root)

    # Then: its exact kinds, image identity, and namespace neutrality are typed.
    image_prefix = "ghcr.io/belltigerlee/smurf-child@sha256:"
    image_digest = "4f4b1535e8a79a9b84518a236fca8e7497c2d0f08d6c1d9d63f01813f8f2a152"
    assert inventory.kinds == ("ConfigMap", "Deployment", "Service")
    assert inventory.images == (f"{image_prefix}{image_digest}",)
    assert inventory.namespace_neutral is True


def test_manifest_rejects_nonexistent_path(tmp_path: Path) -> None:
    # Given: a manifest path that does not exist.
    manifest_path = tmp_path / "missing.yaml"

    # When: the path is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: absence has its own typed category.
    assert caught.value.category is ContractErrorCategory.MANIFEST_NOT_FOUND


def test_manifest_rejects_malformed_yaml() -> None:
    # Given: a malformed Kubernetes YAML fixture.
    manifest_path = Path("tests/fixtures/adversarial/malformed-manifest.yaml")

    # When: the manifest is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: syntax failure has its own typed category.
    assert caught.value.category is ContractErrorCategory.MANIFEST_MALFORMED


def test_manifest_rejects_namespace_kind() -> None:
    # Given: a well-formed Namespace fixture.
    manifest_path = Path("tests/fixtures/adversarial/namespace.yaml")

    # When: the manifest is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: the forbidden kind is categorized.
    assert caught.value.category is ContractErrorCategory.FORBIDDEN_KIND


def test_manifest_rejects_mutable_image() -> None:
    # Given: a Deployment using a mutable image tag.
    manifest_path = Path("tests/fixtures/adversarial/mutable-image.yaml")

    # When: the manifest is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: mutable identity is categorized.
    assert caught.value.category is ContractErrorCategory.IMMUTABLE_IMAGE


def test_manifest_rejects_karmada_policy() -> None:
    # Given: a child-owned Karmada policy fixture.
    manifest_path = Path("tests/fixtures/adversarial/karmada-policy.yaml")

    # When: the manifest is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: the policy kind is categorized as forbidden.
    assert caught.value.category is ContractErrorCategory.FORBIDDEN_KIND


def test_manifest_rejects_non_yaml_format() -> None:
    # Given: a syntactically valid JSON Kubernetes object.
    manifest_path = Path("tests/fixtures/adversarial/deployment.json")

    # When: the manifest is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest_path)

    # Then: source format is rejected independently of content.
    assert caught.value.category is ContractErrorCategory.FORBIDDEN_FORMAT


@pytest.mark.parametrize(
    ("kind", "pod_spec", "container_field", "image_line"),
    [
        ("Deployment", "template:\n    spec:", "containers", ""),
        ("Deployment", "template:\n    spec:", "initContainers", "image: 123"),
        ("Deployment", "template:\n    spec:", "ephemeralContainers", ""),
        ("Job", "template:\n    spec:", "containers", ""),
        (
            "CronJob",
            "jobTemplate:\n    spec:\n      template:\n        spec:",
            "containers",
            "",
        ),
    ],
)
def test_workload_rejects_missing_or_non_string_image(
    kind: str,
    pod_spec: str,
    container_field: str,
    image_line: str,
    tmp_path: Path,
) -> None:
    # Given: an allowed workload with an invalid pod container image.
    manifest = tmp_path / "workload.yaml"
    indent = "          " if kind == "CronJob" else "      "
    image = f"\n{indent}    {image_line}" if image_line else ""
    _ = manifest.write_text(
        "".join(
            (
                f"apiVersion: batch/v1\nkind: {kind}\nmetadata: {{name: sample}}\n",
                f"spec:\n  {pod_spec}\n{indent}{container_field}:\n",
                f"{indent}  - name: sample{image}\n",
            )
        ),
        encoding="utf-8",
    )

    # When: every pod container list is validated.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest)

    # Then: absent and non-string images fail closed.
    assert caught.value.category is ContractErrorCategory.IMMUTABLE_IMAGE
