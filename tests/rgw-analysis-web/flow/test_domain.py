from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from smurf_flow.dataset import DATASET_BYTES, analyze_rows, parse_csv
from smurf_flow.errors import InputDataError
from smurf_flow.models import AnalysisResult, canonical_json, parse_run_id
from smurf_flow.render import ReportValues, WebAssets, render_result_html

WEB_ASSETS = WebAssets(
    directory=Path(__file__).parents[3] / "src" / "rgw-analysis-web" / "web"
)


def test_dataset_has_five_deterministic_rows_when_parsed() -> None:
    # Given: the canonical immutable dataset
    key = "input/dataset.csv"

    # When: its CSV boundary is parsed and analyzed
    rows = parse_csv(key, DATASET_BYTES)
    result = analyze_rows(rows)

    # Then: the stable metrics preserve exact decimal semantics
    assert tuple(row.record_id for row in rows) == (1, 2, 3, 4, 5)
    assert result == AnalysisResult(
        rowCount=5,
        amountSum=Decimal("150.00"),
        amountAverage=Decimal("30.00"),
    )
    assert canonical_json(result) == (
        b'{"amountAverage":"30.00","amountSum":"150.00","rowCount":5}\n'
    )


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (b"wrong,header\n1,x\n", "unexpected CSV header"),
        (b"record_id,label,amount\n1,x,NaN\n", "malformed CSV row"),
        (b"record_id,label,amount\n1,x,-1.00\n", "malformed CSV row"),
        (b"record_id,label,amount\n1,x,1.001\n", "malformed CSV row"),
        (
            b"record_id,label,amount\n1,x,1.00\n1,y,2.00\n",
            "duplicate record_id",
        ),
    ],
)
def test_csv_is_rejected_when_boundary_contract_is_malformed(
    payload: bytes,
    reason: str,
) -> None:
    # Given: malformed untrusted CSV bytes
    key = "input/malformed.csv"

    # When: the boundary parser is invoked
    with pytest.raises(InputDataError) as captured:
        _ = parse_csv(key, payload)

    # Then: a typed error identifies the contract class without echoing content
    assert captured.value.reason == reason
    assert "NaN" not in str(captured.value)


@pytest.mark.parametrize("run_id", ["", "UPPER", "-edge", "edge-", "a/b", "a..b"])
def test_run_id_is_rejected_when_not_a_safe_object_segment(run_id: str) -> None:
    # Given: an unsafe or non-canonical run identifier
    # When/Then: parsing rejects it before path construction
    with pytest.raises(ValidationError):
        _ = parse_run_id(run_id)


def test_html_escapes_object_identity_when_rendered() -> None:
    # Given: trusted metrics and an untrusted-looking source key
    result = AnalysisResult(
        rowCount=1,
        amountSum=Decimal("1.00"),
        amountAverage=Decimal("1.00"),
    )

    # When: the static result is rendered
    rendered = render_result_html(
        WEB_ASSETS,
        ReportValues.from_result("run-1", result, ("input/<script>.csv",)),
    )

    # Then: semantic content is present and executable markup is absent
    assert b'data-field="row-count">1</dd>' in rendered
    assert b'class="report"' in rendered
    assert b"<style>" in rendered
    assert b"input/&lt;script&gt;.csv" in rendered
    assert b"<script>" not in rendered
