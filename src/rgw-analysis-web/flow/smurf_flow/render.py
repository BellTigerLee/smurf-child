"""Deterministic binding of validated static viewer assets."""

import base64
import hashlib
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Final, Self

from smurf_flow.errors import WebAssetError
from smurf_flow.models import AnalysisResult, RunId

TEMPLATE_NAME: Final = "index.template.html"
STYLESHEET_NAME: Final = "report.css"
FAVICON_NAME: Final = "favicon.svg"
STYLESHEET_LINK: Final = '<link rel="stylesheet" href="/report.css" />'
FAVICON_REFERENCE: Final = 'href="/favicon.svg"'
STYLE_POLICY: Final = "style-src 'self'"
TEMPLATE_SLOTS: Final = (
    "__ROW_COUNT__",
    "__AMOUNT_SUM__",
    "__AMOUNT_AVERAGE__",
    "__RUN_ID__",
    "__SOURCE_KEY__",
    "__GENERATED_AT__",
)
TEMPLATE_BINDINGS: Final = (
    *TEMPLATE_SLOTS,
    STYLESHEET_LINK,
    FAVICON_REFERENCE,
    STYLE_POLICY,
)
TEMPLATE_BINDING_PATTERN: Final = re.compile(
    "|".join(
        re.escape(binding)
        for binding in sorted(TEMPLATE_BINDINGS, key=len, reverse=True)
    )
)


@dataclass(frozen=True, slots=True)
class WebAssets:
    """Filesystem boundary for the three trusted viewer source assets."""

    directory: Path

    def load(self) -> "AssetBundle":
        """Read and validate one complete asset generation."""
        template = _read_text(self.directory / TEMPLATE_NAME)
        stylesheet = _read_text(self.directory / STYLESHEET_NAME)
        favicon = _read_bytes(self.directory / FAVICON_NAME)
        _validate_template(self.directory / TEMPLATE_NAME, template)
        _validate_stylesheet(self.directory / STYLESHEET_NAME, stylesheet)
        _validate_favicon(self.directory / FAVICON_NAME, favicon)
        return AssetBundle(
            template=template,
            stylesheet=stylesheet,
            favicon=favicon,
        )


@dataclass(frozen=True, slots=True)
class AssetBundle:
    """Validated exact bytes required for one self-contained report."""

    template: str
    stylesheet: str
    favicon: bytes


@dataclass(frozen=True, slots=True)
class ReportValues:
    """Six text-only values bound into the static report template."""

    row_count: str
    amount_sum: str
    amount_average: str
    run_id: str
    source_key: str
    generated_at: str

    @classmethod
    def from_result(
        cls,
        run_id: RunId,
        result: AnalysisResult,
        source_keys: tuple[str, ...],
    ) -> Self:
        """Format typed analysis values without introducing wall-clock state."""
        return cls(
            row_count=str(result.row_count),
            amount_sum=f"{result.amount_sum:.2f}",
            amount_average=f"{result.amount_average:.2f}",
            run_id=run_id,
            source_key=", ".join(source_keys),
            generated_at="Not recorded",
        )


def render_result_html(assets: WebAssets, values: ReportValues) -> bytes:
    """Bind escaped values and inline validated CSS/favicon deterministically."""
    bundle = assets.load()
    inline_css = f"\n{bundle.stylesheet}"
    style_digest = base64.b64encode(
        hashlib.sha256(inline_css.encode()).digest()
    ).decode("ascii")
    slot_values = dict(
        zip(
            TEMPLATE_SLOTS,
            (
                values.row_count,
                values.amount_sum,
                values.amount_average,
                values.run_id,
                values.source_key,
                values.generated_at,
            ),
            strict=True,
        ),
    )
    favicon_data = base64.b64encode(bundle.favicon).decode("ascii")
    replacements = {
        **{slot: escape(value, quote=True) for slot, value in slot_values.items()},
        STYLESHEET_LINK: f"<style>{inline_css}</style>",
        STYLE_POLICY: f"style-src 'sha256-{style_digest}'",
        FAVICON_REFERENCE: f'href="data:image/svg+xml;base64,{favicon_data}"',
    }

    def replace_binding(match: re.Match[str]) -> str:
        return replacements[match.group(0)]

    document = TEMPLATE_BINDING_PATTERN.sub(replace_binding, bundle.template)
    return document.encode()


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise WebAssetError(path=str(path), reason="missing-or-unreadable") from error


def _read_text(path: Path) -> str:
    payload = _read_bytes(path)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WebAssetError(path=str(path), reason="not-utf-8") from error


def _validate_template(path: Path, template: str) -> None:
    if any(template.count(item) != 1 for item in TEMPLATE_BINDINGS):
        raise WebAssetError(path=str(path), reason="malformed-template-contract")


def _validate_stylesheet(path: Path, stylesheet: str) -> None:
    if not stylesheet.strip() or "</style" in stylesheet.casefold():
        raise WebAssetError(path=str(path), reason="malformed-stylesheet")


def _validate_favicon(path: Path, favicon: bytes) -> None:
    if not favicon.lstrip().startswith(b"<svg"):
        raise WebAssetError(path=str(path), reason="malformed-favicon")
