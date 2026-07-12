from pathlib import Path

import pytest

from smurf_child.contract import parse_request, validate_manifests
from smurf_child.models import ContractErrorCategory, ContractValidationError


@pytest.mark.parametrize(
    "document",
    [
        "apiVersion: v1\nkind: ConfigMap\nmetadata: &m {name: x}\ndata: *m\n",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\ndata:\n  x: 1.2\n",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: x
data:
  x: 2026-07-12
""",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\ndata: !!binary YQ==\n",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: x
data: !!set {x: null}
""",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\ndata: !custom x\n",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: x
data:
  ? [x]
  : y
""",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n---\nkind: Service\n",
        "apiVersion: v1\nkind: ConfigMap\nkind: Service\nmetadata:\n  name: x\n",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\ndata:\n  x: yes\n",
    ],
)
def test_manifest_rejects_non_json_yaml(document: str, tmp_path: Path) -> None:
    # Given: YAML syntax outside the closed JSON-compatible subset.
    manifest = tmp_path / "invalid.yaml"
    _ = manifest.write_text(document, encoding="utf-8")

    # When: the document crosses the manifest boundary.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest)

    # Then: it fails as malformed YAML rather than being implicitly coerced.
    assert caught.value.category is ContractErrorCategory.MANIFEST_MALFORMED


def test_request_rejects_duplicate_key(tmp_path: Path) -> None:
    # Given: an otherwise valid request with a duplicate target key.
    request = tmp_path / "request.yaml"
    _ = request.write_text(
        """apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-one
childId: child-one
workloadId: workload-one
environment: dev
target: b
target: c
""",
        encoding="utf-8",
    )

    # When: the request crosses the YAML boundary.
    with pytest.raises(ContractValidationError) as caught:
        _ = parse_request(request)

    # Then: duplicate keys cannot silently override signed intent.
    assert caught.value.category is ContractErrorCategory.REQUEST_MALFORMED


@pytest.mark.parametrize("scalar", ["012", "+12", "1:20", "~", "Null", ""])
def test_manifest_rejects_noncanonical_implicit_scalar(
    scalar: str, tmp_path: Path
) -> None:
    # Given: a plain scalar spelling that JSON does not permit.
    manifest = tmp_path / "implicit.yaml"
    _ = manifest.write_text(
        f"""apiVersion: v1
kind: ConfigMap
metadata: {{name: sample}}
data:
  value: {scalar}
""",
        encoding="utf-8",
    )

    # When: the scalar crosses the YAML boundary.
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_manifests(manifest)

    # Then: implicit coercion is rejected.
    assert caught.value.category is ContractErrorCategory.MANIFEST_MALFORMED
