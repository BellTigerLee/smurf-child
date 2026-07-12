from pathlib import Path

import pytest
from typer.testing import CliRunner

from smurf_child.handoff import HandoffCategory, HandoffState, evaluate_handoff
from smurf_child.handoff_cli import app


def safe_state() -> HandoffState:
    return HandoffState(
        destination_ref="refs/heads/poc/smurfx-child-dev-contract",
        operations=("push",),
        staged_paths=("src/smurf_child/handoff.py", "tests/test_handoff_guard.py"),
        allowed_paths=("src/smurf_child/handoff.py", "tests/test_handoff_guard.py"),
        sensitive_paths=(),
        excluded_repo_changes=(),
        authored_python_loc=(("src/smurf_child/handoff.py", 120),),
        schema_current=True,
        expected_fixture_sha="e0ae1277cf2090478748f0e9c4a073da6a4ffa81",
        fixture_sha="e0ae1277cf2090478748f0e9c4a073da6a4ffa81",
    )


@pytest.mark.parametrize(
    ("change", "category"),
    [
        ({"destination_ref": "refs/heads/main"}, HandoffCategory.DIRECT_MAIN),
        ({"operations": ("push", "merge")}, HandoffCategory.MERGE_OPERATION),
        ({"staged_paths": (".",)}, HandoffCategory.BROAD_STAGING),
        ({"sensitive_paths": ("tmp/id_ed25519",)}, HandoffCategory.PRIVATE_MATERIAL),
        (
            {"excluded_repo_changes": ("excluded:dirty",)},
            HandoffCategory.EXCLUDED_REPO_DIFF,
        ),
        (
            {"authored_python_loc": (("src/too_large.py", 251),)},
            HandoffCategory.PYTHON_LOC,
        ),
        ({"schema_current": False}, HandoffCategory.STALE_SCHEMA),
        ({"fixture_sha": "0" * 40}, HandoffCategory.FIXTURE_SHA),
    ],
)
def test_handoff_rejects_unsafe_input(
    change: dict[str, str | bool | tuple[str, ...] | tuple[tuple[str, int], ...]],
    category: HandoffCategory,
) -> None:
    state = safe_state().model_copy(update=change)

    rejection = evaluate_handoff(state)

    assert rejection is not None
    assert rejection.category is category


def test_handoff_accepts_exact_feature_preflight() -> None:
    assert evaluate_handoff(safe_state()) is None


def test_cli_reports_category_from_input_document(tmp_path: Path) -> None:
    state_path = tmp_path / "handoff.json"
    _ = state_path.write_text(
        safe_state().model_copy(update={"schema_current": False}).model_dump_json(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, [str(state_path)])

    assert result.exit_code == 1
    assert result.stdout == "HANDOFF_REJECTED[STALE_SCHEMA]\n"
