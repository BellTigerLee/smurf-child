import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

WEB_ROOT: Final = Path(__file__).parents[3] / "src" / "rgw-analysis-web" / "web"
COLOR_PATTERN: Final = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True, slots=True)
class ContrastPair:
    foreground: str
    background: str
    minimum: float


TEXT_PAIRS: Final = [
    ContrastPair("--color-ink", "--color-canvas", 4.5),
    ContrastPair("--color-ink", "--color-paper", 4.5),
    ContrastPair("--color-ink-secondary", "--color-paper", 4.5),
    ContrastPair("--color-ink-secondary", "--color-surface-muted", 4.5),
    ContrastPair("--color-ink-quiet", "--color-paper", 4.5),
    ContrastPair("--color-ink-quiet", "--color-surface-muted", 4.5),
    ContrastPair("--color-success-ink", "--color-success-surface", 4.5),
    ContrastPair("--color-waiting-ink", "--color-waiting-surface", 4.5),
    ContrastPair("--color-error-ink", "--color-error-surface", 4.5),
]
FOCUS_PAIRS: Final = [
    ContrastPair("--color-focus", "--color-canvas", 3.0),
    ContrastPair("--color-focus", "--color-paper", 3.0),
]


def token_value(stylesheet: str, token: str) -> str:
    prefix = f"{token}:"
    assignment = next(
        (
            line.strip()
            for line in stylesheet.splitlines()
            if line.strip().startswith(prefix)
        ),
        None,
    )
    assert assignment is not None, f"Missing color token: {token}"
    value = assignment.removeprefix(prefix).removesuffix(";").strip()
    assert COLOR_PATTERN.fullmatch(value) is not None
    return value


def linear_channel(value: int) -> float:
    normalized = value / 255
    if normalized <= 0.04045:
        return normalized / 12.92
    return math.pow((normalized + 0.055) / 1.055, 2.4)


def relative_luminance(color: str) -> float:
    red = linear_channel(int(color[1:3], 16))
    green = linear_channel(int(color[3:5], 16))
    blue = linear_channel(int(color[5:7], 16))
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def contrast_ratio(pair: ContrastPair, stylesheet: str) -> float:
    foreground = relative_luminance(token_value(stylesheet, pair.foreground))
    background = relative_luminance(token_value(stylesheet, pair.background))
    lighter = max(foreground, background)
    darker = min(foreground, background)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("pair", [*TEXT_PAIRS, *FOCUS_PAIRS])
def test_wcag_contrast_when_used_color_pair_is_rendered(pair: ContrastPair) -> None:
    given_stylesheet = (WEB_ROOT / "report.css").read_text(encoding="utf-8")

    when_ratio = contrast_ratio(pair, given_stylesheet)

    assert when_ratio >= pair.minimum, (
        f"{pair.foreground} on {pair.background} is {when_ratio:.3f}:1; "
        f"expected at least {pair.minimum:.1f}:1"
    )
