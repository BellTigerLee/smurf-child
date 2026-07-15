from html import escape
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError
from smurf_flow.errors import WebAssetError
from smurf_flow.models import DEFAULT_WEB_ASSETS_PATH, WebAssetSettings
from smurf_flow.render import ReportValues, WebAssets, render_result_html

WEB_ROOT: Final = Path(__file__).parents[3] / "src" / "rgw-analysis-web" / "web"
SLOTS: Final = (
    "__ROW_COUNT__",
    "__AMOUNT_SUM__",
    "__AMOUNT_AVERAGE__",
    "__RUN_ID__",
    "__SOURCE_KEY__",
    "__GENERATED_AT__",
)


def values(prefix: str = "value") -> ReportValues:
    return ReportValues(
        row_count=f"<{prefix}-rows>",
        amount_sum=f"<{prefix}-sum>",
        amount_average=f"<{prefix}-average>",
        run_id=f"<{prefix}-run>",
        source_key=f"<{prefix}-source>",
        generated_at=f"<{prefix}-generated>",
    )


def copy_assets(target: Path) -> None:
    for name in ("index.template.html", "report.css", "favicon.svg"):
        _ = (target / name).write_bytes((WEB_ROOT / name).read_bytes())


def test_renderer_binds_todo3_template_css_and_favicon_deterministically() -> None:
    # Given: the confirmed Todo 3 asset generation and six report values
    assets = WebAssets(directory=WEB_ROOT)
    report = values("stable")

    # When: the same report is rendered twice
    first = render_result_html(assets, report)
    second = render_result_html(assets, report)

    # Then: output is identical, self-contained, and has no unresolved slot
    assert first == second
    assert b'class="report"' in first
    assert b"<style>\n:root" in first
    assert b"report.css" not in first
    assert b"data:image/svg+xml;base64," in first
    assert b"style-src &#x27;sha256-" not in first
    assert b"style-src 'sha256-" in first
    assert all(slot.encode() not in first for slot in SLOTS)


def test_renderer_escapes_every_dynamic_template_value() -> None:
    # Given: markup-shaped text in every one of the six template values
    report = values("script")

    # When: the trusted template is bound
    rendered = render_result_html(WebAssets(directory=WEB_ROOT), report)

    # Then: every value remains text and creates no executable element
    assert rendered.count(b"&lt;script-") == 6
    assert b"<script-" not in rendered
    assert b"<script>" not in rendered


def test_renderer_never_rescans_slot_tokens_inserted_as_user_text() -> None:
    # Given: every field contains HTML metacharacters and every other slot token
    field_values = tuple(
        f"field-{index} & < > \" ' "
        + "|".join(token for token in SLOTS if token != own_slot)
        for index, own_slot in enumerate(SLOTS)
    )
    report = ReportValues(*field_values)

    # When: the template is bound once
    rendered = render_result_html(WebAssets(directory=WEB_ROOT), report)

    # Then: all six inserted values retain their exact escaped text
    expected = tuple(escape(value, quote=True).encode() for value in field_values)
    assert all(value in rendered for value in expected)
    assert b"field-0 &amp; &lt; &gt; &quot; &#x27;" in rendered


def test_renderer_fails_closed_when_required_asset_is_missing(tmp_path: Path) -> None:
    # Given: an asset directory without the required template
    # When/Then: typed validation fails before report publication
    with pytest.raises(WebAssetError) as captured:
        _ = render_result_html(WebAssets(directory=tmp_path), values())
    assert captured.value.reason == "missing-or-unreadable"


@pytest.mark.parametrize(
    ("asset", "payload", "reason"),
    [
        ("index.template.html", b"\xff", "not-utf-8"),
        ("index.template.html", b"<html></html>", "malformed-template-contract"),
        ("report.css", b"</style><script>", "malformed-stylesheet"),
        ("favicon.svg", b"not-svg", "malformed-favicon"),
    ],
)
def test_renderer_fails_closed_when_asset_contract_is_malformed(
    tmp_path: Path,
    asset: str,
    payload: bytes,
    reason: str,
) -> None:
    # Given: a complete asset directory with one malformed member
    copy_assets(tmp_path)
    _ = (tmp_path / asset).write_bytes(payload)

    # When/Then: no partial document is returned
    with pytest.raises(WebAssetError) as captured:
        _ = render_result_html(WebAssets(directory=tmp_path), values())
    assert captured.value.reason == reason


def test_web_asset_setting_has_absolute_container_default_and_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: no override, then an explicit absolute runtime mount
    monkeypatch.delenv("SMURF_WEB_ASSETS_PATH", raising=False)
    default = WebAssetSettings.model_validate({})
    monkeypatch.setenv("SMURF_WEB_ASSETS_PATH", str(tmp_path))

    # When: runtime settings are parsed again
    overridden = WebAssetSettings.model_validate({})

    # Then: the image contract is stable and the mount is typed
    assert default.directory == DEFAULT_WEB_ASSETS_PATH
    assert default.directory == Path("/opt/smurf-flow/web")
    assert overridden.directory == tmp_path


def test_web_asset_setting_rejects_relative_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a working-directory-dependent runtime override
    monkeypatch.setenv("SMURF_WEB_ASSETS_PATH", "relative/web")

    # When/Then: settings reject it before filesystem access
    with pytest.raises(ValidationError):
        _ = WebAssetSettings.model_validate({})
