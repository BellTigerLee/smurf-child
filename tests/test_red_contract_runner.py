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
    with pytest.raises(InventoryMismatchError, match="node inventory mismatch"):
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


def test_red_inventory_rejects_green_or_collection_exit() -> None:
    # Given: a complete result set paired with a non-contract pytest exit.
    records = _records_from_expected()

    # When: pytest reports success or collection failure.
    for exit_code in (0, 2):
        with pytest.raises(InventoryMismatchError, match="expected pytest exit 1"):
            verify_inventory(records, exit_code=exit_code)

    # Then: only the exact intentional test-failure exit is accepted.
