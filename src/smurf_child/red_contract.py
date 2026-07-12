"""Exact intentional-RED inventory verifier for the Task 2 scaffold."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, Literal

from defusedxml import ElementTree

type TestStatus = Literal["failed", "passed"]


@dataclass(frozen=True, slots=True)
class ExpectedTest:
    """One expected pytest node, status, and diagnostic signature."""

    node_id: str
    status: TestStatus
    signature: str | None = None


@dataclass(frozen=True, slots=True)
class ObservedTest:
    """One observed pytest node from JUnit output."""

    node_id: str
    status: TestStatus
    diagnostic: str


class InventoryMismatchError(RuntimeError):
    """Raised when pytest differs from the complete intentional RED inventory."""


REQUEST_FAILURES: Final = (
    "test_request_parses_inert_identity_and_both_target",
    "test_request_parses_each_literal_target[b]",
    "test_request_parses_each_literal_target[c]",
    "test_request_parses_each_literal_target[both]",
    "test_request_rejects_nonexistent_file",
    "test_request_rejects_malformed_yaml",
    "test_request_rejects_invalid_schema",
    "test_request_rejects_child_owned_effective_policy",
)
MANIFEST_FAILURES: Final = (
    "test_dev_bundle_returns_namespace_neutral_digest_inventory",
    "test_manifest_rejects_nonexistent_path",
    "test_manifest_rejects_malformed_yaml",
    "test_manifest_rejects_namespace_kind",
    "test_manifest_rejects_mutable_image",
    "test_manifest_rejects_karmada_policy",
    "test_manifest_rejects_non_yaml_format",
)
QUALITY_NODE_PREFIX: Final = "tests/test_contract_test_quality.py::"
EXPECTED_TESTS: Final = (
    *(
        ExpectedTest(
            f"tests/test_request_contract.py::{name}",
            "failed",
            "PLANNED_UNIMPLEMENTED:REQUEST_PARSER",
        )
        for name in REQUEST_FAILURES
    ),
    *(
        ExpectedTest(
            f"tests/test_manifest_contract.py::{name}",
            "failed",
            "PLANNED_UNIMPLEMENTED:MANIFEST_VALIDATOR",
        )
        for name in MANIFEST_FAILURES
    ),
    ExpectedTest(
        "tests/test_cli.py::test_validate_reports_success_for_repository_contract",
        "failed",
        "assert 2 == 0",
    ),
    ExpectedTest(
        "tests/test_cli.py::test_validate_reports_named_error_without_traceback",
        "failed",
        "FORBIDDEN_KIND",
    ),
    ExpectedTest(
        f"{QUALITY_NODE_PREFIX}test_request_assertions_reject_accept_all_none",
        "passed",
    ),
    ExpectedTest(
        f"{QUALITY_NODE_PREFIX}test_manifest_assertions_reject_accept_all_none",
        "passed",
    ),
)
TEST_MODULES: Final = (
    "tests/test_request_contract.py",
    "tests/test_manifest_contract.py",
    "tests/test_cli.py",
    "tests/test_contract_test_quality.py",
)


def verify_inventory(records: tuple[ObservedTest, ...], exit_code: int) -> None:
    """Require the exact node, status, signature, count, and pytest exit code."""
    expected_count = len(EXPECTED_TESTS)
    if len(records) != expected_count:
        message = (
            f"observed record count: expected {expected_count}, got {len(records)}"
        )
        raise InventoryMismatchError(message)
    observed_node_ids = tuple(record.node_id for record in records)
    if len(set(observed_node_ids)) != expected_count:
        message = "duplicate observed node IDs"
        raise InventoryMismatchError(message)
    expected_by_node = {test.node_id: test for test in EXPECTED_TESTS}
    observed_by_node = {record.node_id: record for record in records}
    if exit_code != 1:
        message = f"expected pytest exit 1, observed {exit_code}"
        raise InventoryMismatchError(message)
    if observed_by_node.keys() != expected_by_node.keys():
        missing = sorted(expected_by_node.keys() - observed_by_node.keys())
        extra = sorted(observed_by_node.keys() - expected_by_node.keys())
        message = f"RED node inventory mismatch: missing={missing}, extra={extra}"
        raise InventoryMismatchError(message)
    for node_id, expected in expected_by_node.items():
        observed = observed_by_node[node_id]
        if observed.status != expected.status:
            message = f"{node_id}: expected {expected.status}, got {observed.status}"
            raise InventoryMismatchError(message)
        if (
            expected.signature is not None
            and expected.signature not in observed.diagnostic
        ):
            message = f"{node_id}: missing diagnostic {expected.signature!r}"
            raise InventoryMismatchError(message)


def read_junit(report: Path) -> tuple[ObservedTest, ...]:
    """Read pytest JUnit into stable node/status/diagnostic records."""
    root = ElementTree.parse(report).getroot()
    if root is None:
        message = "pytest JUnit report has no root element"
        raise InventoryMismatchError(message)
    records: list[ObservedTest] = []
    for case in root.iter("testcase"):
        class_name = case.attrib["classname"]
        test_name = case.attrib["name"]
        failure = case.find("failure")
        status: TestStatus = "failed" if failure is not None else "passed"
        diagnostic = "" if failure is None else failure.attrib.get("message", "")
        path = class_name.replace(".", "/") + ".py"
        records.append(ObservedTest(f"{path}::{test_name}", status, diagnostic))
    return tuple(records)


def main() -> None:
    """Run pytest and reject any drift from the complete intentional inventory."""
    with TemporaryDirectory(prefix="smurf-child-red-") as directory:
        report = Path(directory) / "report.xml"
        completed = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--junitxml={report}",
                *TEST_MODULES,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        _ = sys.stdout.write(completed.stdout)
        _ = sys.stderr.write(completed.stderr)
        verify_inventory(read_junit(report), completed.returncode)
    message = (
        f"EXPECTED_RED_INVENTORY_PASS tests={len(EXPECTED_TESTS)} "
        "failures=17 passes=2\n"
    )
    _ = sys.stdout.write(message)
