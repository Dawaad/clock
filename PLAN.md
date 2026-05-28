# clock — terminal countdown timer

A `clock <duration>` CLI that renders a high-fidelity animated countdown in the
terminal: a gradient circular ring (red→orange→yellow) with radial tick dots, a
vertical tick scale, a large remaining-time readout, a header showing the
current wall time and date, an elapsed line, and live controls.

Reference starting point: `~/Downloads/ringtimer.py` (braille dot-canvas
renderer). This plan extends it toward the image-3 dial aesthetic.

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
  cli.py          # arg parsing, entry point
  parse.py        # parse_duration() + format_hms()
  theme.py        # colors, constants, Layout dataclass (derived from size)
  canvas.py       # Canvas + draw_arc/tick_marks primitives + coalesced emit
  state.py        # TimerState dataclass + apply_key reducer + clock source
  render.py       # pure render(state, size) -> str (cached static layers)
  app.py          # Textual App + custom widget, ~10fps, key bindings
tests/
  test_parse.py
  test_render.py
  test_state.py
  test_app.py     # Textual Pilot smoke
pyproject.toml
```

## Render composition (image-3 fidelity)

- Circular gradient ring (clockwise arc = fraction remaining) + radial tick dots.
- Vertical tick scale (right rail) with a moving progress indicator.
- Big remaining-time number (hh:mm:ss / mm:ss / seconds), centered.
- Header: current wall time + date.
- Elapsed line (REC-style indicator).
- Bottom control hint.

## Build order

1. Scaffold package + pyproject (Textual dep).
2. `parse.py` + exhaustive parser tests (9A).
3. `state.py` (TimerState, apply_key reducer, injected clock) + tests (11A/12A).
4. `theme.py` + `canvas.py` (primitives, coalesced emit) (6A/8A/16A).
5. `render.py` (pure, cached static layers) + structural/golden tests (10A/13A).
6. `app.py` (Textual app, widget, bindings, fps) + Pilot smoke (11A/14A).
7. `cli.py` entry point wiring (4A/7A).
8. Manual run-through; install verification.
