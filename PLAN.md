# clock — four-panel terminal countdown timer

A `clock <duration>` CLI rendering a flat, editorial four-quadrant panel
(cream paper / dark ink), in a bordered box split 2×2:

- **Top-left — TIMER:** big remaining readout + a horizontal "equalizer"
  progress bar that fills with elapsed time, plus a RUNNING/PAUSED status.
- **Top-right — KEYBINDS:** the available controls.
- **Bottom-left — CLOCK:** a circular braille progress ring (remaining) with a
  dial pointer and a percentage.
- **Bottom-right — TIME:** real-world wall time, year, weekday and date.

Rendered with a small flat cell buffer (`raster.Frame`) plus a tiny braille
canvas (`braille`) for the ring. No external rendering deps beyond Textual.

The prior 3D radio-dial design was fully scrapped for this layout.

## Controls

`space`/`p` pause · `+`/`-` adjust ±10s · `q` quit

## Usage

```
clock 30        # 30 seconds
clock 5s        # 5 seconds
clock 5m        # 5 minutes
clock 2.5h      # 2.5 hours
clock 30:00     # mm:ss
clock 1:00:00   # h:mm:ss
```

Controls: `space`/`p` pause, `+`/`-` adjust ±10s, `q` quit.

## Decisions (from feature-plan review)

| # | Area | Decision |
|---|------|----------|
| 1 | Module structure | Right-sized package `clock/` (cli, parse, render, app, …) |
| 2 | State/render | `TimerState` dataclass + pure `render(state, size) -> str` |
| 3 | Input/platform | Textual TUI framework for loop/input/resize; custom braille widget |
| 4 | Packaging | `pyproject.toml` console_script `clock = clock.cli:main` |
| 5 | Duration parsing | Full explicit spec'd parser + validation + friendly errors |
| 6 | Drawing DRY | Extract `draw_arc` / `tick_marks` stroke primitives |
| 7 | Edge cases | hh:mm:ss display, validated input, NO_COLOR/non-tty fallback |
| 8 | Constants | `theme.py` constants + computed `Layout` dataclass |
| 9 | Parser tests | Exhaustive parametrized table (valid/invalid/boundary) |
| 10 | Render tests | Structural assertions + a few fixed-size golden snapshots |
| 11 | Control tests | Pure `apply_key` reducer unit tests + Textual Pilot smoke |
| 12 | Time determinism | Inject a clock source; fake it in tests |
| 13 | Static track | Cache static layers per size; redraw only arc/number |
| 14 | Frame rate | ~10fps via Textual interval; number on second boundaries |
| 15 | Canvas structure | Keep dict-backed Canvas; profile before optimizing |
| 16 | ANSI output | Coalesce consecutive same-color runs in emit |

## Layout

```
clock/
  __init__.py
  cli.py          # arg parsing, entry point (console_script `clock`)
  parse.py        # parse_duration() + format_readout/format_hms
  font.py         # bitmap font for the big readouts
  theme.py        # flat cream/ink palette
  state.py        # TimerState + advance/apply_key/with_now (injected clock)
  raster.py       # flat Frame (char/fg/bg) + coalesced ANSI emit
  braille.py      # tiny braille Canvas for the clock ring
  ui.py           # render(state, size) -> str  (four-quadrant panel)
  app.py          # Textual App: clocks, keys, ~10fps refresh
tests/            # parse, state, raster, ui, app, cli
tools/preview.py  # dev: rasterize a frame to PNG for visual review
pyproject.toml
```

## Adaptive / responsive layout

The renderer is fully size-driven and recomputes on every frame (Textual
`on_resize` triggers a redraw):

- **Wide (≥ 64 cols):** the 2×2 grid with asymmetric columns — top-left timer
  and bottom-right time are the wide panels; top-right keybinds and bottom-left
  clock are narrower (matching the reference).
- **Narrow (< 64 cols):** the grid collapses to a single stacked column
  (timer → keybinds → clock → time). When the stack is taller than the viewport
  it is rendered at full height inside a `VerticalScroll`; arrows / PageUp-Down /
  Home / End scroll it. The clock band flexes to fill any spare height.
- Each big readout uses the block font when it fits, else plain text.
- Below ~24×10 a centred "WINDOW TOO SMALL" message is shown.
