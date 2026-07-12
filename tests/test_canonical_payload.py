import hashlib
import json
import struct
from pathlib import Path

import pytest
import rfc8785
from pydantic import TypeAdapter, ValidationError

from smurf_child.bundle import build_bundle
from smurf_child.evidence import EvidenceInput, build_evidence
from smurf_child.yaml_boundary import JsonValue

_JSON_MAP: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


def test_bundle_uses_exact_framing_and_utf8_path_order(tmp_path: Path) -> None:
    # Given: two valid manifests whose path order differs by UTF-8 bytes.
    root = tmp_path / "repo"
    deploy = root / "deploy" / "dev"
    deploy.mkdir(parents=True)
    documents = {
        "deploy/dev/a.yaml": {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "a"},
        },
        "deploy/dev/z.yaml": {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "z"},
        },
    }
    for path, document in documents.items():
        _ = (root / path).write_bytes(rfc8785.dumps(document))

    # When: the bundle is canonicalized.
    bundle = build_bundle(root, tuple(reversed(tuple(documents))))

    # Then: independent framing reconstruction is byte-identical with no suffix.
    expected = bytearray(b"SMURFX-BUNDLE\0v1\0")
    expected.extend(struct.pack(">I", 2))
    for path in sorted(documents, key=lambda value: value.encode()):
        path_bytes = path.encode()
        document_bytes = rfc8785.dumps(documents[path])
        expected.extend(struct.pack(">I", len(path_bytes)))
        expected.extend(path_bytes)
        expected.extend(struct.pack(">Q", len(document_bytes)))
        expected.extend(document_bytes)
    assert bundle.bytes == bytes(expected)
    assert bundle.digest == f"sha256:{hashlib.sha256(expected).hexdigest()}"


def test_evidence_payload_is_canonical_and_non_self_referential() -> None:
    # Given: deterministic signed-domain CI metadata and derived source values.
    evidence_input = EvidenceInput.model_validate(
        {
            "workflow_issuer": "https://token.actions.githubusercontent.com",
            "workflow_subject": (
                "repo:BellTigerLee/smurf-child:ref:refs/heads/"
                "poc/smurfx-child-dev-contract"
            ),
            "workflow_name": "validate",
            "run_id": "1001",
            "repository": "git@github.com:BellTigerLee/smurf-child.git",
            "path": "deploy/dev",
            "sha": "a" * 40,
            "build_passed": True,
            "tests_passed": True,
            "bundle_digest": f"sha256:{'b' * 64}",
            "image_digests": (f"sha256:{'c' * 64}",),
            "started_at": "2026-07-12T06:00:00.000000Z",
            "completed_at": "2026-07-12T06:01:00.000000Z",
        }
    )

    # When: unsigned evidence is generated twice.
    first = build_evidence(evidence_input)
    second = build_evidence(evidence_input)

    # Then: bytes and digest are deterministic and exclude envelope/self fields.
    assert first == second
    assert b"evidenceDigest" not in first.payload
    assert b"signature" not in first.payload
    assert b"signerKeyId" not in first.payload
    framed = (
        b"SMURFX-EVIDENCE\0v1\0" + struct.pack(">Q", len(first.payload)) + first.payload
    )
    assert first.digest == f"sha256:{hashlib.sha256(framed).hexdigest()}"


def test_evidence_payload_uses_exact_camel_case_wire_fields() -> None:
    # Given: a valid evidence input using internal Python names.
    evidence_input = _valid_evidence_input()

    # When: the signed-domain payload is canonicalized.
    payload = _JSON_MAP.validate_python(
        json.loads(build_evidence(evidence_input).payload), strict=True
    )

    # Then: its wire keys match the contract exactly and contain no snake case.
    assert tuple(payload) == (
        "buildPassed",
        "bundleDigest",
        "completedAt",
        "imageDigests",
        "path",
        "repository",
        "runId",
        "sourceSha",
        "startedAt",
        "testsPassed",
        "workflowIssuer",
        "workflowName",
        "workflowSubject",
    )
    assert payload["buildPassed"] is True
    assert payload["testsPassed"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_issuer", ""),
        ("workflow_subject", ""),
        ("workflow_name", ""),
        ("run_id", ""),
        ("repository", "https://github.com/BellTigerLee/smurf-child.git"),
        ("path", "./deploy/dev"),
        ("sha", "a" * 39),
        ("image_digests", ("not-a-digest",)),
        ("image_digests", (f"sha256:{'c' * 64}", f"sha256:{'c' * 64}")),
        ("started_at", "2026-07-12T06:00:00Z"),
    ],
)
def test_evidence_input_rejects_invalid_contract_field(
    field: str, value: str | tuple[str, ...]
) -> None:
    # Given: one malformed signed-domain field.
    candidate = _valid_evidence_input().model_dump()
    candidate[field] = value

    # When/Then: strict boundary parsing rejects the candidate.
    with pytest.raises(ValidationError):
        _ = EvidenceInput.model_validate(candidate)


def test_evidence_input_rejects_unknown_and_wire_named_input() -> None:
    # Given: unknown or wire-case fields presented to the Python boundary.
    candidate = _valid_evidence_input().model_dump()
    candidate["signature"] = "forbidden"
    candidate["sourceSha"] = candidate.pop("sha")

    # When/Then: closed input rejects both additions.
    with pytest.raises(ValidationError):
        _ = EvidenceInput.model_validate(candidate)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-13-01T00:00:00.000000Z",
        "2026-04-31T00:00:00.000000Z",
        "2025-02-29T00:00:00.000000Z",
        "2026-01-01T24:00:00.000000Z",
        "2026-01-01T23:60:00.000000Z",
        "2026-01-01T23:59:60.000000Z",
    ],
)
@pytest.mark.parametrize("field", ["started_at", "completed_at"])
def test_evidence_input_rejects_semantically_invalid_timestamp(
    field: str, timestamp: str
) -> None:
    # Given: exact timestamp syntax containing an impossible calendar/time value.
    candidate = _valid_evidence_input().model_dump()
    candidate[field] = timestamp

    # When/Then: semantic timestamp validation rejects the exact field.
    with pytest.raises(ValidationError) as caught:
        _ = EvidenceInput.model_validate(candidate)
    assert caught.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("started_at", "completed_at"),
    [
        ("2024-02-29T00:00:00.000000Z", "2024-02-29T00:00:00.000001Z"),
        ("2026-12-31T23:59:59.999998Z", "2026-12-31T23:59:59.999999Z"),
    ],
)
def test_evidence_input_preserves_valid_edge_timestamps(
    started_at: str, completed_at: str
) -> None:
    # Given: valid leap-day or end-of-day timestamps in exact wire form.
    candidate = _valid_evidence_input().model_dump()
    candidate["started_at"] = started_at
    candidate["completed_at"] = completed_at

    # When: the evidence boundary parses and serializes the values.
    parsed = EvidenceInput.model_validate(candidate)
    payload = build_evidence(parsed).payload

    # Then: no normalization changes the signed timestamp text.
    assert parsed.started_at == started_at
    assert parsed.completed_at == completed_at
    assert f'"startedAt":"{started_at}"'.encode() in payload
    assert f'"completedAt":"{completed_at}"'.encode() in payload


def _valid_evidence_input() -> EvidenceInput:
    return EvidenceInput.model_validate(
        {
            "workflow_issuer": "https://token.actions.githubusercontent.com",
            "workflow_subject": "repo:BellTigerLee/smurf-child:ref:refs/heads/poc",
            "workflow_name": "validate",
            "run_id": "1001",
            "repository": "git@github.com:BellTigerLee/smurf-child.git",
            "path": "deploy/dev",
            "sha": "a" * 40,
            "build_passed": True,
            "tests_passed": True,
            "bundle_digest": f"sha256:{'b' * 64}",
            "image_digests": (f"sha256:{'c' * 64}",),
            "started_at": "2026-07-12T06:00:00.000000Z",
            "completed_at": "2026-07-12T06:01:00.000000Z",
        }
    )
