from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Final, override

import pytest

REPOSITORY_ROOT: Final = Path(__file__).parents[3]
WEB_ROOT: Final = REPOSITORY_ROOT / "src" / "rgw-analysis-web" / "web"
DOCUMENTS: Final = (
    WEB_ROOT / "index.template.html",
    WEB_ROOT / "fixtures" / "loading.html",
    WEB_ROOT / "fixtures" / "empty.html",
    WEB_ROOT / "fixtures" / "error.html",
    WEB_ROOT / "fixtures" / "success.html",
)
EXPECTED_CSP_PARTS: Final = (
    "default-src 'none'",
    "style-src 'self'",
    "img-src 'self' data:",
    "base-uri 'none'",
    "form-action 'none'",
    "object-src 'none'",
)
TEMPLATE_SLOTS: Final = (
    "__ROW_COUNT__",
    "__AMOUNT_SUM__",
    "__AMOUNT_AVERAGE__",
    "__RUN_ID__",
    "__SOURCE_KEY__",
    "__GENERATED_AT__",
)


@dataclass(frozen=True, slots=True)
class TagRecord:
    name: str
    attributes: tuple[tuple[str, str | None], ...]


class DocumentProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[TagRecord] = []
        self.text_fragments: list[str] = []

    @override
    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.tags.append(TagRecord(name=tag, attributes=tuple(attrs)))

    @override
    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.tags.append(TagRecord(name=tag, attributes=tuple(attrs)))

    @override
    def handle_data(self, data: str) -> None:
        normalized = data.strip()
        if normalized:
            self.text_fragments.append(normalized)


def parse_document(path: Path) -> DocumentProbe:
    probe = DocumentProbe()
    probe.feed(path.read_text(encoding="utf-8"))
    probe.close()
    return probe


def attribute_value(record: TagRecord, name: str) -> str | None:
    return next((value for key, value in record.attributes if key == name), None)


def tags_named(probe: DocumentProbe, name: str) -> list[TagRecord]:
    return [record for record in probe.tags if record.name == name]


def tag_with_attribute(
    probe: DocumentProbe,
    attribute: str,
    value: str,
) -> TagRecord | None:
    return next(
        (
            record
            for record in probe.tags
            if attribute_value(record, attribute) == value
        ),
        None,
    )


@pytest.mark.parametrize("document", DOCUMENTS)
def test_semantic_landmarks_when_document_is_loaded(document: Path) -> None:
    given_root = parse_document(document)

    when_headings = tags_named(given_root, "h1")
    when_html = tags_named(given_root, "html")
    when_article = tags_named(given_root, "article")

    assert len(when_html) == 1
    assert attribute_value(when_html[0], "lang") == "en"
    assert len(when_headings) == 1
    assert "RGW Analysis Result" in given_root.text_fragments
    assert len(tags_named(given_root, "main")) == 1
    assert len(when_article) == 1
    assert attribute_value(when_article[0], "aria-labelledby") == "report-title"


@pytest.mark.parametrize("document", DOCUMENTS)
def test_security_boundary_when_document_is_loaded(document: Path) -> None:
    given_source = document.read_text(encoding="utf-8")
    given_root = parse_document(document)

    when_csp = tag_with_attribute(
        given_root,
        "http-equiv",
        "Content-Security-Policy",
    )
    when_resources = (*tags_named(given_root, "link"), *tags_named(given_root, "img"))

    assert when_csp is not None
    content = attribute_value(when_csp, "content")
    assert content is not None
    assert all(part in content for part in EXPECTED_CSP_PARTS)
    assert tags_named(given_root, "script") == []
    assert tags_named(given_root, "form") == []
    assert "javascript:" not in given_source.casefold()
    assert "http://" not in given_source.casefold()
    assert "https://" not in given_source.casefold()
    assert all(
        not (
            attribute_value(resource, "href") or attribute_value(resource, "src") or ""
        ).startswith("//")
        for resource in when_resources
    )


@pytest.mark.parametrize("document", DOCUMENTS)
def test_metadata_when_document_is_loaded(document: Path) -> None:
    given_root = parse_document(document)

    when_title = tags_named(given_root, "title")
    when_viewport = tag_with_attribute(given_root, "name", "viewport")
    when_description = tag_with_attribute(given_root, "name", "description")
    when_stylesheet = tag_with_attribute(given_root, "rel", "stylesheet")
    when_icon = tag_with_attribute(given_root, "rel", "icon")

    assert len(when_title) == 1
    assert when_viewport is not None
    assert (
        attribute_value(when_viewport, "content")
        == "width=device-width, initial-scale=1"
    )
    assert when_description is not None
    assert when_stylesheet is not None
    stylesheet_href = attribute_value(when_stylesheet, "href")
    assert stylesheet_href is not None
    assert stylesheet_href.endswith("report.css")
    assert when_icon is not None
    assert attribute_value(when_icon, "href") is not None
    assert (WEB_ROOT / "favicon.svg").is_file()


@pytest.mark.parametrize(
    "case",
    [
        ("loading.html", "loading", "status", "true"),
        ("empty.html", "empty", "region", "false"),
        ("error.html", "error", "alert", "false"),
        ("success.html", "success", "region", "false"),
    ],
)
def test_state_contract_when_fixture_is_loaded(
    case: tuple[str, str, str, str],
) -> None:
    fixture_name, state, role, busy = case
    given_root = parse_document(WEB_ROOT / "fixtures" / fixture_name)

    when_article = tags_named(given_root, "article")[0]
    when_status = tag_with_attribute(given_root, "data-component", "status-rail")

    assert when_status is not None
    assert attribute_value(when_article, "data-state") == state
    assert attribute_value(when_article, "aria-busy") == busy
    assert attribute_value(when_status, "role") == role
    assert state.capitalize() in given_root.text_fragments


def test_result_contract_when_success_fixture_is_loaded() -> None:
    given_root = parse_document(WEB_ROOT / "fixtures" / "success.html")

    when_labels = [
        label
        for label in ("Rows", "Amount sum", "Amount average")
        if label in given_root.text_fragments
    ]
    when_values = [
        value
        for value in ("5", "150.00", "30.00")
        if value in given_root.text_fragments
    ]

    assert when_labels == ["Rows", "Amount sum", "Amount average"]
    assert when_values == ["5", "150.00", "30.00"]


def test_escaping_boundary_when_success_fixture_contains_hostile_source() -> None:
    given_root = parse_document(WEB_ROOT / "fixtures" / "success.html")

    assert tag_with_attribute(given_root, "data-field", "source-key") is not None
    assert 'input/<script>alert("x")</script>.csv' in given_root.text_fragments
    assert tags_named(given_root, "script") == []


def test_template_contract_when_producer_renders_result() -> None:
    given_source = (WEB_ROOT / "index.template.html").read_text(encoding="utf-8")

    assert all(given_source.count(field) == 1 for field in TEMPLATE_SLOTS)
    assert "__ROWS_HTML__" not in given_source
    assert "__MESSAGE_HTML__" not in given_source


def test_design_tokens_when_stylesheet_is_loaded() -> None:
    given_source = (WEB_ROOT / "report.css").read_text(encoding="utf-8")

    when_forbidden = (
        "linear-gradient",
        "radial-gradient",
        "box-shadow",
        "animation:",
        "url(",
    )

    assert "--color-canvas: #f7f6f3;" in given_source
    assert "--space-1: 0.25rem;" in given_source
    assert ":focus-visible" in given_source
    assert "@media (min-width: 48rem)" in given_source
    assert "@media (min-width: 64rem)" in given_source
    assert all(token not in given_source for token in when_forbidden)
