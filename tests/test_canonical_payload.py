import hashlib
import struct
from pathlib import Path

import rfc8785

from smurf_child.bundle import build_bundle
from smurf_child.evidence import EvidenceInput, build_evidence


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
    evidence_input = EvidenceInput(
        workflow_issuer="https://token.actions.githubusercontent.com",
        workflow_subject="repo:BellTigerLee/smurf-child:ref:refs/heads/poc/smurfx-child-dev-contract",
        workflow_name="validate",
        run_id="1001",
        repository="git@github.com:BellTigerLee/smurf-child.git",
        path="deploy/dev",
        sha="a" * 40,
        build_result="success",
        test_result="success",
        bundle_digest=f"sha256:{'b' * 64}",
        image_digests=(f"sha256:{'c' * 64}",),
        started_at="2026-07-12T06:00:00.000000Z",
        completed_at="2026-07-12T06:01:00.000000Z",
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
