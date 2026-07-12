from pathlib import Path

from smurf_child.contract import validate_manifests


def test_dev_bundle_accepts_namespace_neutral_plain_resources() -> None:
    # Given: the repository's plain Deployment, Service, and ConfigMap bundle.
    deploy_root = Path("deploy/dev")

    # When: the manifest boundary validates the bundle.
    validate_manifests(deploy_root)

    # Then: RED records that manifest-set behavior is not implemented.


def test_dev_bundle_requires_digest_pinned_images() -> None:
    # Given: a Deployment intended to use immutable image identity.
    deploy_root = Path("deploy/dev")

    # When: the manifest boundary checks image references.
    validate_manifests(deploy_root, behavior="immutable_image")

    # Then: RED records that immutable-image behavior is not implemented.


def test_dev_bundle_rejects_forbidden_formats() -> None:
    # Given: a directory contract that permits regular YAML files only.
    deploy_root = Path("deploy/dev")

    # When: the manifest boundary checks source formats.
    validate_manifests(deploy_root, behavior="forbidden_format")

    # Then: RED records that forbidden-format behavior is not implemented.
