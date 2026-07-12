from dataclasses import replace

import pytest

from smurf_child.red_contract import (
    EXPECTED_TESTS,
    InventoryMismatchError,
    ObservedTest,
    verify_inventory,
)


def _records_from_expected() -> tuple[ObservedTest, ...]:
    return tuple(
        ObservedTest(
            expected.node_id,
            expected.status,
            expected.signature or "",
        )
        for expected in EXPECTED_TESTS
    )


def test_red_inventory_accepts_only_complete_expected_results() -> None:
    # Given: one record for every expected node and exact signature.
    records = _records_from_expected()

    # When: the complete intentional inventory is checked.
    verify_inventory(records, exit_code=1)

    # Then: no mismatch is raised.


def test_red_inventory_rejects_one_test_only_simulation() -> None:
    # Given: the old runner's false-positive shape containing one planned failure.
    records = _records_from_expected()[:1]

    # When: the incomplete inventory is checked.
    with pytest.raises(InventoryMismatchError, match="observed record count"):
        verify_inventory(records, exit_code=1)

    # Then: missing tests cannot satisfy the RED gate.


def test_red_inventory_rejects_unrelated_failure() -> None:
    # Given: all nodes with one diagnostic replaced by an unrelated failure.
    records = _records_from_expected()
    unrelated = replace(records[0], diagnostic="RuntimeError: unrelated")

    # When: the misleading inventory is checked.
    with pytest.raises(InventoryMismatchError, match="missing diagnostic"):
        verify_inventory((unrelated, *records[1:]), exit_code=1)

    # Then: generic nonzero pytest results cannot satisfy the RED gate.


def test_red_inventory_rejects_extra_unique_record() -> None:
    # Given: the exact inventory plus one unknown unique node.
    records = _records_from_expected()
    extra = replace(records[0], node_id="tests/test_extra.py::test_unexpected")

    # When: the 20-record inventory is checked.
    with pytest.raises(InventoryMismatchError, match="observed record count"):
        verify_inventory((*records, extra), exit_code=1)

    # Then: extra unique nodes cannot be normalized away.


def test_red_inventory_rejects_wrong_status() -> None:
    # Given: the exact nodes with one expected failure reported as passed.
    records = _records_from_expected()
    wrong_status = replace(records[0], status="passed")

    # When: the status-drifted inventory is checked.
    with pytest.raises(InventoryMismatchError, match="expected failed, got passed"):
        verify_inventory((wrong_status, *records[1:]), exit_code=1)

    # Then: node presence cannot hide status drift.


def test_red_inventory_rejects_duplicate_twentieth_record() -> None:
    # Given: the exact 19 records plus a duplicate of the first node.
    records = _records_from_expected()

    # When: the 20-record inventory is checked.
    with pytest.raises(InventoryMismatchError, match="observed record count"):
        verify_inventory((*records, records[0]), exit_code=1)

    # Then: dictionary normalization cannot hide a duplicate node.


def test_red_inventory_rejects_duplicate_with_expected_count() -> None:
    # Given: 19 records with the final node replaced by a duplicate first node.
    records = _records_from_expected()

    # When: the duplicate-node inventory is checked.
    with pytest.raises(InventoryMismatchError, match="duplicate observed node IDs"):
        verify_inventory((*records[:-1], records[0]), exit_code=1)

    # Then: uniqueness is checked independently from total count.


def test_red_inventory_rejects_green_or_collection_exit() -> None:
    # Given: a complete result set paired with a non-contract pytest exit.
    records = _records_from_expected()

    # When: pytest reports success or collection failure.
    for exit_code in (0, 2):
        with pytest.raises(InventoryMismatchError, match="expected pytest exit 1"):
            verify_inventory(records, exit_code=exit_code)

    # Then: only the exact intentional test-failure exit is accepted.
