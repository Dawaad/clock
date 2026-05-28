# Tabbed / focus-section redesign — design spec

Date: 2026-05-28
Branch: `tabs`

## Goal

Replace the static four-quadrant dashboard (TIMER + KEYBINDS, then CLOCK | TIME |
STOPWATCH) with a **focus-driven section layout**:

- No dedicated KEYBINDS panel. Each section shows its own keybind strip at its top.
- Sections are all visible at once; one is **active**. Arrow keys move the active
  highlight between sections.
- Keys are **contextual**: e.g. focus the STOPWATCH section and `space` toggles
  it (replacing the global `s`); focus the TIMER and `space` pauses/resumes.
- TIMER and the progress ring (old CLOCK quadrant) merge into one top section,
  shown side by side.
- TIME expands to digital time **plus** an analog "reflective" clock.

## Locked decisions (from review)

| Area | Decision |
|------|----------|
| Layout model | **1A** sections all visible, moving focus highlight |
| Focus state | **2A** immutable `View`/`Section` dataclass in `state.py`, threaded into `render()` |
| Key dispatch | **3A** pure `dispatch(section, key) -> action`; `on_key` is a thin router |
| Arrow keys | **4A** arrows navigate; focused section auto-scrolls into view |
| Key sources | **5A** one keybind registry; config/ui/dispatch all derive from it |
| Routing scope | **6A** route everything through `dispatch`, globals via a `GLOBAL` section |
| Section chrome | **7A** single `_section` primitive: border + header + keybind strip + focus highlight |
| Layout geometry | **8A** small, pure, tested section-list height distributor |
| Test migration | **9A** rewrite old-model tests with explicit old→new mapping |
| Pure-unit tests | **10A** full coverage incl. wrap, unknown-key, GLOBAL-from-any, layout overflow + rounding |
| Registry guard | **11A** invariant tests (no dup key per section, GLOBAL non-collision, every Action reachable) |
| Behavioral tests | **12A** focus nav, auto-scroll-to-focus, contextual space, analog determinism + time-sensitivity |
| Idle redraw | **13B** skip `from_ansi` + `update` when the emitted frame is unchanged |
| Analog motion | **14A** hands jump per-second (idle frames stay identical, cooperates with 13B) |

### Contract decisions

- **`+` / `-` (adjust 10s): timer-focused-only.** They do nothing unless the
  TIMER section is active. Consistent with contextual `space`.
- **Focus navigation wraps around.** Past the last section returns to the first
  (cyclic), and vice versa.

## Components

### `state.py`

- `class Section(Enum)`: `TIMER`, `STOPWATCH`, `TIME` (the focusable sections),
  plus `GLOBAL` (a pseudo-section for keys that work regardless of focus).
- `@dataclass(frozen=True) class View`: `active: Section = Section.TIMER`.
- `focus_next(view) -> View` / `focus_prev(view) -> View`: cycle through the
  ordered focusable sections (excludes `GLOBAL`), wrapping at the ends.
- `dispatch(section, key) -> Action | None`: resolve a Textual key name in the
  context of the active section to an `Action`. GLOBAL bindings take precedence
  (or are checked alongside section bindings); unknown keys return `None`.
- `class Action(Enum)`: `PAUSE`, `ADJUST_UP`, `ADJUST_DOWN`, `SET_TIMER`,
  `CLEAR`, `QUIT`, `SW_TOGGLE`, `FOCUS_NEXT`, `FOCUS_PREV`.

The existing `PAUSE_KEYS` / `ADD_KEYS` / `SUB_KEYS` char-sets are removed; their
job is subsumed by the registry + `dispatch`.

### Keybind registry (single source of truth — 5A)

One structure (likely in `config.py` or a new `keys.py`) mapping each `Action`
to `(default Textual keys, display label, owning Section)`. Everything derives
from it:

- `config.py` builds the user-overridable keybind map (per action) from the
  registry defaults.
- `ui.py` reads display labels + owning section to render each section's keybind
  strip.
- `dispatch` resolves `(section, key) -> action` from the (user-merged) registry.

Per-section bindings (defaults):

- **TIMER**: `space` pause/resume, `+`/`-` adjust 10s, `c` clear (only when a
  timer is active).
- **STOPWATCH**: `space` start/pause, `c` reset (when running or elapsed > 0).
- **TIME**: (no section-specific actions; arrows/global only.)
- **GLOBAL**: arrows focus nav, `e` set timer, `q` quit.

User config keeps action-named overrides; `dispatch` stays contextual.

### `ui.py`

- `_section(f, rect, title, keybinds, active, co)`: draws the border, header,
  the keybind strip at the top, and an accent focus highlight when `active`.
  Each section function draws **only its content** inside the inner rect.
- `_layout(sections, avail_rows) -> list[rect]`: pure distributor. Each section
  declares a min-height and optional flex; distribute available rows, flex
  sections absorb slack, the sum of heights equals `avail_rows` exactly. When
  `avail_rows < sum(min_heights)`, return the natural (min) heights so the app
  can scroll the overflow (consistent with today's stacked-scroll behavior).
- TIMER section: digital remaining + elapsed equalizer bar **and** the progress
  ring (old `_clock_quadrant`) side by side.
- TIME section: digital `%H:%M` + date, **plus** an analog clock drawn on the
  braille `Canvas` (hour + minute + second hands). Hands computed from
  `state.now`; second hand jumps per second (14A).
- STOPWATCH section: unchanged content (status + big readout).
- `render(state, size, view, stopwatch, colors)` gains the `view` argument so it
  knows which section to highlight.

### `app.py`

- `self.view = View()`; arrow keys produce `FOCUS_NEXT` / `FOCUS_PREV`.
- `on_key`: `action = dispatch(self.view.active, event.key)`; a single
  `_apply(action)` switch performs the effect (pause, adjust, toggle stopwatch,
  set timer, clear, quit, focus move). No more if-ladder, no hardcoded `s`/`c`,
  no `_SCROLL_KEYS`, no `_ACTION_TOKENS`.
- After a focus change, **auto-scroll the focused section into view** (4A) in the
  narrow/stacked mode (replaces manual scroll keys).
- `_draw`: cache the last emitted frame string; if `render(...)` returns an
  identical string, skip `Text.from_ansi` + `widget.update` (13B).

## Data flow

```
tick (fps) ─▶ advance/sw_tick/with_now (state.py) ─▶ render(state, size, view, sw, co)
key event  ─▶ dispatch(view.active, key) ─▶ Action ─▶ _apply ─▶ (mutate state/view) ─▶ _draw
_draw: render -> emit string; if == last: skip; else from_ansi + update
```

`render`, `dispatch`, `focus_next/prev`, and `_layout` are all pure and unit-tested.

## Testing plan

- **Pure units (10A):** `focus_next/prev` wrap-around; `dispatch` unknown-key→None,
  GLOBAL key from every section, `+`/`-` only resolve under TIMER; `_layout`
  overflow (avail < sum min) and exact-sum/flex rounding.
- **Registry invariants (11A):** no two bindings share a key within a section;
  GLOBAL keys collide with no section key; every `Action` is reachable.
- **Behavioral (12A, pilot):** arrow changes `view.active`; narrow mode scrolls
  the focused section into view; `space` pauses when TIMER focused and toggles
  the stopwatch when STOPWATCH focused; `+`/`-` no-op unless TIMER focused;
  analog render is deterministic and differs across times while digital `%H:%M`
  still shows.
- **Migration (9A):** explicit old→new mapping, e.g.
  - `test_all_quadrant_headers_present` → headers for TIMER/STOPWATCH/TIME (no KEYBINDS)
  - `test_keybinds_listed` → `test_section_keybind_strips`
  - `test_clear_bind_shown_only_with_active_timer` → same, scoped to TIMER strip
  - `test_s_key_toggles_stopwatch` → `test_space_toggles_focused_stopwatch`
  - `test_narrow_viewport_is_scrollable` → `test_focus_autoscrolls_into_view`
  - preserve: teardown safety, theme backdrop, unconfigured-doesn't-advance,
    rebound-quit, countdown-advances.

## Out of scope

- No Textual `Tabs`/widget rewrite (we keep the pure braille/raster `render()`).
- No general layout engine beyond the small section-list distributor.
- No dirty-region/partial-redraw machinery (13B skip-unchanged only).
- No config schema change beyond what the registry requires; existing
  action-named overrides keep working.
