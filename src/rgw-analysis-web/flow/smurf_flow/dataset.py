"""Deterministic CSV generation and exact decimal analysis."""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation, localcontext
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smurf_flow.errors import InputDataError
from smurf_flow.models import AnalysisResult

DATASET_BYTES: Final = (
    b"record_id,label,amount\n"
    b"1,alpha,10.00\n"
    b"2,beta,20.00\n"
    b"3,gamma,30.00\n"
    b"4,delta,40.00\n"
    b"5,epsilon,50.00\n"
)
EXPECTED_COLUMNS: Final = ("record_id", "label", "amount")
CENT: Final = Decimal("0.01")


class CsvRow(BaseModel):
    """One validated input row crossing the CSV trust boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    record_id: int = Field(ge=1)
    label: str = Field(min_length=1)
    amount: Decimal = Field(ge=0, decimal_places=2, allow_inf_nan=False)


def parse_csv(key: str, payload: bytes) -> tuple[CsvRow, ...]:
    """Parse UTF-8 CSV bytes into unique, typed rows."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputDataError(key=key, reason="input is not UTF-8") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise InputDataError(key=key, reason="unexpected CSV header")

    rows: list[CsvRow] = []
    try:
        rows.extend(CsvRow.model_validate(raw) for raw in reader)
    except (ValidationError, InvalidOperation) as error:
        raise InputDataError(key=key, reason="malformed CSV row") from error

    if not rows:
        raise InputDataError(key=key, reason="CSV contains no data rows")
    identifiers = tuple(row.record_id for row in rows)
    if len(identifiers) != len(set(identifiers)):
        raise InputDataError(key=key, reason="duplicate record_id")
    return tuple(rows)


def analyze_rows(rows: tuple[CsvRow, ...]) -> AnalysisResult:
    """Aggregate rows using decimal-128-style half-even arithmetic."""
    with localcontext() as context:
        context.prec = 28
        total = sum((row.amount for row in rows), start=Decimal(0)).quantize(CENT)
        average = (total / Decimal(len(rows))).quantize(CENT)
    return AnalysisResult(
        rowCount=len(rows),
        amountSum=total,
        amountAverage=average,
    )
