# RGW Analysis Web Design System

## 0. Research Log

- Embedded references: shortlisted Notion, Wired, and Claude for a warm, readable
  operational report; selected `minimalist-skill.md` with `notion.md` because the
  surface needs document hierarchy and quiet structure rather than dashboard chrome.
- Lazyweb: attempted three read-only searches for cloud-storage analysis reports,
  data-quality states, and operational job results; the endpoint returned
  `MCP_PRO_REQUIRED`, so no external screens were viewed or copied.
- Imagen drafts: skipped because the approved direction is an operational document,
  the deliverable forbids a rasterized mock, and no decorative imagery is needed.
- Designpowers: the primary personas are an operator checking whether analysis
  completed and a reviewer verifying exact aggregates; accessibility and debt are
  recorded in Section 8.

## 1. Atmosphere & Identity

This is a calm evidence sheet: warm paper, precise ink, and just enough structure to
scan a result without mistaking decoration for data. The signature is a narrow status
rail above a definition-led report, so completion state is understood before any
metric is read. The layout borrows Notion's warm neutrals and whisper borders without
copying its product chrome or brand assets.

## 2. Color

### Palette

| Role | Token | Value | Usage |
| --- | --- | --- | --- |
| Canvas | `--color-canvas` | `#f7f6f3` | Page background |
| Paper | `--color-paper` | `#fffefa` | Report surface |
| Surface muted | `--color-surface-muted` | `#efeee9` | Secondary rows and loading blocks |
| Ink | `--color-ink` | `#2f3437` | Headings and values |
| Ink secondary | `--color-ink-secondary` | `#625f5b` | Descriptions and metadata |
| Ink quiet | `--color-ink-quiet` | `#6b6762` | Supporting labels |
| Border | `--color-border` | `#ddd9d2` | Whisper dividers |
| Focus | `--color-focus` | `#1769aa` | Keyboard focus only |
| Success surface | `--color-success-surface` | `#edf3ec` | Completed state |
| Success ink | `--color-success-ink` | `#346538` | Completed state text |
| Waiting surface | `--color-waiting-surface` | `#fbf3db` | Loading state |
| Waiting ink | `--color-waiting-ink` | `#76520a` | Loading state text |
| Error surface | `--color-error-surface` | `#fdebec` | Error state |
| Error ink | `--color-error-ink` | `#8f302f` | Error text |

### Rules

- Color communicates report state only; it is not decorative.
- Ink and status pairs must meet WCAG 2.2 AA contrast.
- CSS uses these custom properties exclusively. New colors are added here first.
- `tests/rgw-analysis-web/web/test_color_contrast.py` executes the WCAG relative
  luminance formula for every text/surface pairing used by the stylesheet and the
  focus indicator against both page surfaces. Quiet ink measures 5.56:1 on paper
  and 4.83:1 on the muted surface.

## 3. Typography

### Scale

| Level | Token | Size | Weight | Line height | Usage |
| --- | --- | --- | --- | --- | --- |
| Display | `--type-display` | `clamp(2rem, 5vw, 3rem)` | 650 | 1.08 | Page title |
| Heading | `--type-heading` | `1.25rem` | 650 | 1.3 | Section titles |
| Metric | `--type-metric` | `1.75rem` | 650 | 1.15 | Aggregate values |
| Body | `--type-body` | `1rem` | 400 | 1.6 | Reading text |
| Small | `--type-small` | `0.875rem` | 400 | 1.5 | Metadata |
| Label | `--type-label` | `0.75rem` | 650 | 1.4 | Status and field labels |

### Font stacks

- UI and body: `ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- Display: `ui-serif, Georgia, Cambria, "Times New Roman", serif`.
- Data: `ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace`.

No font file or external font request is permitted. Body text never falls below 14px.

## 4. Spacing & Layout

The base unit is 4px.

| Token | Value | Usage |
| --- | --- | --- |
| `--space-1` | `0.25rem` | Tight inline separation |
| `--space-2` | `0.5rem` | Label-to-value spacing |
| `--space-3` | `0.75rem` | Compact row gap |
| `--space-4` | `1rem` | Mobile page inset |
| `--space-5` | `1.25rem` | Panel padding |
| `--space-6` | `1.5rem` | Section gap |
| `--space-8` | `2rem` | Desktop panel padding |
| `--space-10` | `2.5rem` | Major section separation |
| `--space-12` | `3rem` | Desktop page inset |

- Content width is `68rem`; prose measure is `42rem`.
- At 375px the report is one column with 16px insets. At 768px metrics use two
  columns. At 1280px metrics use three columns while the page remains centered.
- Every gap, margin, and padding maps to a declared spacing token.

## 5. Components

### Report frame

- **Structure**: `main > article`, with one `header` and labelled `section` elements.
- **Variants**: loading, empty, error, success.
- **Spacing**: `--space-4`, `--space-6`, `--space-8`, `--space-10`.
- **States**: the article uses `aria-busy="true"` only while waiting.
- **Accessibility**: exactly one `h1`; regions are named by their `h2`.
- **Motion**: none.

### Status rail

- **Structure**: status label, plain-language message, and optional timestamp.
- **Variants**: waiting, empty, error, complete.
- **Spacing**: `--space-3` and `--space-4`.
- **States**: error uses `role="alert"`; waiting uses `role="status"`; complete and
  empty are labelled regions so a static document does not announce stale events.
- **Accessibility**: state is always written in text and never encoded by color alone.
- **Motion**: none; loading does not pulse.

### Metric list

- **Structure**: semantic `dl` containing paired `dt` and `dd` values.
- **Variants**: three aggregate metrics; optional source metadata remains separate.
- **Spacing**: `--space-3`, `--space-4`, and `--space-5`.
- **States**: result, or absent in loading/empty/error fixtures.
- **Accessibility**: values use tabular numerals and remain selectable text.
- **Motion**: none.

### Definition row

- **Structure**: a two-column `dl` row for source URI and generation time.
- **Variants**: standard and wrapped long value.
- **Spacing**: `--space-2`, `--space-3`, and `--space-4`.
- **Accessibility**: URI is text, not an untrusted clickable link.
- **Motion**: none.

## 6. Motion & Interaction

The report is read-only and uses no decorative animation or JavaScript. Browser-native
text selection is the only interaction. `prefers-reduced-motion` is therefore
satisfied by construction.

## 7. Depth & Surface

The strategy is borders-only plus tonal shift. The paper surface uses one whisper
border; sections are separated by the border token or muted surface. There are no
gradients, glass effects, or box shadows. Corners use the fixed functional radius
tokens `--radius-small` (`0.25rem`) and `--radius-panel` (`0.5rem`).

## 8. Accessibility Constraints & Accepted Debt

### Constraints

- Target WCAG 2.2 AA: 4.5:1 for normal text and 3:1 for large text and focus
  indicators.
- Landmarks, headings, descriptions, table semantics, and state announcements must
  remain meaningful without CSS.
- All untrusted source strings are HTML-escaped by the producer before entering the
  template. The template never executes result data as markup or script.
- No credentials, endpoint secrets, access keys, or raw environment data appear.
- The 375px layout has no page-level horizontal overflow.

### Accepted Debt

| Item | Location | Why accepted | Owner / Exit |
| --- | --- | --- | --- |
| Lighthouse and assistive-technology evidence pending | All fixtures | Real Chrome 149 captured all four states at 375/768/1280 and exposed the expected accessibility tree, but Lighthouse and a real screen-reader session have not run | Final visual-QA lane must run Lighthouse and assistive-technology checks before release |

Current local evidence is stored under
`.omo/evidence/smurf-child-scalex-integration/03-result-ui/`. Browser captures and
static semantics are local implementation evidence only; they do not prove deployed
runtime health or assistive-technology compatibility.
