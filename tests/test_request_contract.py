from pathlib import Path

from smurf_child.contract import parse_request


def test_request_accepts_inert_literal_target_metadata() -> None:
    # Given: an inert child request with a literal federation target.
    request_path = Path("smurfx/request.yaml")

    # When: the request boundary parses the file.
    parse_request(request_path)

    # Then: RED records that request-schema behavior is not implemented.


def test_request_derives_stable_ids_without_commit_identity() -> None:
    # Given: a request whose identity is independent from a Git commit.
    request_path = Path("smurfx/request.yaml")

    # When: the request boundary derives stable identifiers.
    parse_request(request_path, behavior="stable_ids")

    # Then: RED records that stable-ID behavior is not implemented.


def test_request_accepts_literal_b_target(tmp_path: Path) -> None:
    # Given: a syntactically valid request using one allowed literal target.
    request_path = tmp_path / "request.yaml"
    _ = request_path.write_text(
        """apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-belltigerlee
childId: smurf-child
workloadId: sample-api
environment: dev
target: b
""",
        encoding="utf-8",
    )

    # When: the request boundary parses the literal.
    parse_request(request_path, behavior="target_literal")

    # Then: RED records that literal-target behavior is not implemented.


def test_request_accepts_literal_c_target(tmp_path: Path) -> None:
    # Given: a syntactically valid request using the c target.
    request_path = tmp_path / "request.yaml"
    _ = request_path.write_text(
        """apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-belltigerlee
childId: smurf-child
workloadId: sample-api
environment: dev
target: c
""",
        encoding="utf-8",
    )

    # When: the request boundary parses the literal.
    parse_request(request_path, behavior="target_literal")

    # Then: RED records that literal-target behavior is not implemented.


def test_request_accepts_literal_both_target(tmp_path: Path) -> None:
    # Given: a syntactically valid request using the both target.
    request_path = tmp_path / "request.yaml"
    _ = request_path.write_text(
        """apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-belltigerlee
childId: smurf-child
workloadId: sample-api
environment: dev
target: both
""",
        encoding="utf-8",
    )

    # When: the request boundary parses the literal.
    parse_request(request_path, behavior="target_literal")

    # Then: RED records that literal-target behavior is not implemented.
