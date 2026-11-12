# Design system

This document is the single reference for how Desktop Organizer looks and behaves.
Every window follows it. Values here are implemented in
`src/desktop_organizer/core/theme.py`; if the two ever disagree, the code is a bug.

## Principles

- Quiet and precise. The interface gets out of the way of the work.
- Native first. Windows 11 behavior and conventions, standard title bar, standard dialogs.
- Dense but readable. Lists, tables and forms, not decorative cards.
- One way to do each thing. The same toolbar, dialog and progress pattern in every tool.

## Color

A neutral grayscale plus one accent. Semantic colors appear only for status (result
messages, validation, progress outcome), never as decoration.

| Token | Light | Dark | Use |
|---|---|---|---|
| `window` | `#F5F5F5` | `#1C1C1C` | Window background |
| `surface` | `#FFFFFF` | `#262626` | Lists, inputs, content areas |
| `surface_alt` | `#EDEDED` | `#303030` | Hover, secondary buttons, table header |
| `surface_pressed` | `#E3E3E3` | `#383838` | Pressed state of neutral controls |
| `divider` | `#E3E3E3` | `#353535` | Separators between regions (non-interactive) |
| `control_border` | `#8F8F8F` | `#7A7A7A` | Borders of inputs and buttons (3:1 against surface) |
| `text` | `#1B1B1B` | `#F0F0F0` | Primary text |
| `text_secondary` | `#5E5E5E` | `#ADADAD` | Descriptions, captions, status line |
| `text_disabled` | `#9E9E9E` | `#727272` | Disabled text |
| `accent` | `#1F5FBF` | `#6CA6EE` | Primary button, focus ring, selection marker, links |
| `accent_hover` | `#1A52A6` | `#86B6F2` | Primary button hover |
| `accent_pressed` | `#15458C` | `#5A93DB` | Primary button pressed |
| `on_accent` | `#FFFFFF` | `#0E1A2B` | Text on accent |
| `selection` | `#DCE6F5` | `#2A3A52` | Selected list row background |
| `success` | `#1E7A3C` | `#62C281` | Status only |
| `warning` | `#8A5A00` | `#E2B252` | Status only |
| `error` | `#C42B1C` | `#FF8F85` | Status only, destructive button |
| `on_error` | `#FFFFFF` | `#2B0E0B` | Text on the destructive button |

Contrast requirements (checked by `tests/test_theme.py`):

- Primary and secondary text, accent and semantic colors: at least 4.5:1 on `window`, `surface` and `surface_alt`.
- Text on accent and on error: at least 4.5:1.
- `control_border`: at least 3:1 on `surface` (WCAG 1.4.11).

## Typography

One family: **Segoe UI Variable** (Windows 11), falling back to **Segoe UI** (Windows 10).
Two weights: Regular (400) and Semibold (600).

| Step | Size | Weight | Use |
|---|---|---|---|
| Caption | 12 px | 400 | Status line, secondary descriptions, group headings (600) |
| Body | 14 px | 400 | Default text, inputs, buttons, list titles (600) |
| Subtitle | 16 px | 600 | Section headings in dialogs and tool windows |
| Title | 20 px | 600 | Tool window heading |
| Display | 28 px | 600 | Reserved for large single values (for example system monitor readings) |

Sizes are logical pixels; Windows display scaling applies on top.

## Spacing and layout

- 8 px grid. Allowed spacing values: 4 (tight pairs only), 8, 12, 16, 24, 32.
- Window content margin: 16 px. Gap between toolbar and content: 12 px.
- Control height: 32 px. List row: 56 px for two-line rows, 36 px for one-line rows.
- Corner radius: 4 px for controls and rows, 6 px for dialogs. Nothing larger.
- No shadows except the native window shadow.

## Iconography

- **Lucide** (ISC license), outline style, stroke 2 on a 24 px grid.
- Rendered at 16 px in buttons and 20 px in lists, tinted with the current text color.
- Icons accompany labels; they never replace a label (exception: the clear button inside a search field, which has an accessible name and tooltip).

## Components

**Primary button.** Accent fill, `on_accent` text, 32 px high, 16 px horizontal padding. At most one per window region.

**Secondary button.** `surface` fill, `control_border` border, `text` color. Hover `surface_alt`, pressed `surface_pressed`.

**Destructive button.** Used only in confirmation dialogs for irreversible actions. `error` fill, `on_error` text.

**Text field and search field.** `surface` fill, 1 px `control_border`, 2 px accent bottom border on focus. Search field has a leading search icon and a clear button.

**Combo box.** Same frame as a text field, chevron-down icon on the right, at least 240 px wide in forms.

**List row.** Icon, title (Body semibold), description (Caption, secondary). Hover `surface_alt`. Selected: `selection` background plus a 3 px accent marker on the left. Disabled rows keep their text readable and show a plain status label on the right ("Not available yet").

**Group heading.** Caption semibold, `text_secondary`, 16 px above, 4 px below.

**Status line.** One line, Caption, `text_secondary`, separated by a `divider` line on top, values joined by a middle dot.

**Dialogs.** Native window frame. Title states the question ("Delete all data?"). Body states the consequence in one or two sentences. Buttons right-aligned, verb-first; the safe action is the default; Esc cancels.

**Progress.** Determinate bar when the total is known, otherwise an indeterminate bar plus a counter ("1,204 files scanned"). Always with a Cancel button. Result shown inline with the matching semantic color and a plain sentence.

## States

| State | Treatment |
|---|---|
| Hover | `surface_alt` background (neutral controls), `accent_hover` (primary) |
| Pressed | `surface_pressed` (neutral), `accent_pressed` (primary) |
| Focus (keyboard) | 2 px `accent` outline or bottom border; always visible |
| Selected | `selection` background, 3 px accent marker |
| Disabled | `text_disabled` text, no hover reaction |
| Error | `error` text and border on the affected field, message below the field |

## Motion

Only where it explains a change, under 150 ms, and none when Windows "Animation effects" is off. The foundation uses no animation.

## Writing

- Sentence case everywhere. No exclamation marks, no emojis, no marketing words.
- Buttons start with a verb: "Scan folder", "Create backup", "Delete all data".
- Error messages say what happened and what to do next: "The folder could not be read. Check that the drive is connected."
- Empty states say what is missing and how to fill it.
- German and English strings live in `src/desktop_organizer/resources/i18n/`; no UI text in code.

## Keyboard

- Every action reachable by keyboard, logical tab order, visible focus.
- Esc closes tool windows and dialogs. Enter triggers the default button.
- Overview: Ctrl+F focuses search, Down moves from search into the list, Enter opens a tool, Ctrl+, opens settings.
