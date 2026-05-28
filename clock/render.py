"""Pure rendering: TimerState + terminal size -> ANSI string.

``render`` is deterministic given its inputs, so frames can be snapshot-tested.
The static dial chrome (gray track, radial ticks, rail) depends only on size,
so it is computed once per size and cloned per frame.
"""

from __future__ import annotations

import math

from . import theme
from .canvas import Canvas, draw_arc, emit_grid, radial_ticks, vertical_ticks
from .font import compose_number as _compose_number
from .parse import format_hms, format_readout
from .state import TimerState
from .theme import Layout

Cell = tuple[str, theme.RGB]
Grid = list[list[Cell | None]]

_static_cache: dict[tuple[int, int], Canvas] = {}


def _rail_geom(layout: Layout) -> tuple[float, float, float]:
    """Right anchor (dot x) and top/bottom (dot y) of the vertical rail."""
    x_right = layout.rail_col * 2 + 1
    y0 = 4.0
    y1 = layout.body_rows * 4 - 4
    return x_right, y0, y1


def _static_canvas(layout: Layout) -> Canvas:
    key = (layout.cols, layout.rows)
    cached = _static_cache.get(key)
    if cached is not None:
        return cached

    canvas = Canvas(layout.cols, layout.body_rows)
    # Gray track: full circle.
    draw_arc(
        canvas, layout.cx, layout.cy, layout.radius, layout.thick,
        0, 2 * math.pi, theme.TRACK, layer=0,
    )
    # Faint radial tick marks just outside the ring.
    r_out = layout.radius + layout.thick / 2 + 2
    radial_ticks(
        canvas, layout.cx, layout.cy, r_out, r_out + 2,
        theme.RADIAL_TICKS, theme.dim(theme.TRACK, 0.7), layer=0,
    )
    # Vertical rail of gray ticks.
    x_right, y0, y1 = _rail_geom(layout)
    vertical_ticks(
        canvas, x_right, y0, y1, theme.RAIL_TICKS, theme.RAIL_LONG,
        short_len=4, long_len=8, color=theme.TRACK, layer=0,
    )
    _static_cache[key] = canvas
    return canvas


def _put_text(grid: Grid, row: int, col: int, text: str, color: theme.RGB) -> None:
    if not (0 <= row < len(grid)):
        return
    width = len(grid[row])
    for i, ch in enumerate(text):
        c = col + i
        if 0 <= c < width:
            grid[row][c] = (ch, color)


def _too_small(layout: Layout) -> str:
    grid: Grid = [[None] * layout.cols for _ in range(layout.rows)]
    msg = "WINDOW TOO SMALL"
    _put_text(grid, layout.rows // 2, max(0, (layout.cols - len(msg)) // 2),
              msg, theme.LABEL)
    return emit_grid(grid)


def render(state: TimerState, size: tuple[int, int]) -> str:
    cols, rows = size
    layout = Layout.from_size(cols, rows)
    if layout.too_small:
        return _too_small(layout)

    canvas = _static_canvas(layout).clone()

    # Gradient progress arc (clockwise from the top), dimmed while paused.
    frac = state.fraction
    if frac > 0:
        arc_color = (
            (lambda t: theme.dim(theme.grad(t), 0.4))
            if state.paused else theme.grad
        )
        draw_arc(
            canvas, layout.cx, layout.cy, layout.radius, layout.thick,
            0, 2 * math.pi * frac, arc_color, layer=1,
        )

    # Rail indicator: descends from full (top) to empty (bottom).
    x_right, y0, y1 = _rail_geom(layout)
    y_ind = y0 + (y1 - y0) * (1 - frac)
    for dxi in range(12):
        canvas.dot(x_right - dxi, y_ind, theme.REC, layer=2)

    grid: Grid = [[None] * cols for _ in range(rows)]
    canvas.blit_into(grid)

    _overlay_text(grid, state, layout)
    return emit_grid(grid)


def _overlay_text(grid: Grid, state: TimerState, layout: Layout) -> None:
    body_rows = layout.body_rows
    center_x = layout.rail_col // 2
    center_y = body_rows // 2

    # Header: current time + date (top-left of the dial area).
    _put_text(grid, 1, 3, state.now.strftime("%I:%M %p").lstrip("0"),
              theme.HEADER)
    _put_text(grid, 2, 3, state.now.strftime("%b %d, %A"), theme.LABEL)

    # Big readout, centred in the ring.
    num = _compose_number(format_readout(state.remaining), layout.scale)
    nh, nw = len(num), max(len(r) for r in num)
    top = center_y - nh // 2 - 1
    left = center_x - nw // 2
    for r, line in enumerate(num):
        for c, ch in enumerate(line):
            if ch == "#":
                gy, gx = top + r, left + c
                if 0 <= gy < body_rows and 0 <= gx < layout.cols:
                    grid[gy][gx] = ("█", theme.WHITE)

    # Label under the number.
    label = "PAUSED" if state.paused else (
        "SECONDS" if state.total_seconds < 60 else "REMAINING"
    )
    label_color = theme.WHITE if state.paused else theme.LABEL
    _put_text(grid, top + nh + 1, center_x - len(label) // 2, label, label_color)

    # Elapsed (REC-style) indicator beneath the label.
    elapsed = f"● REC  {format_hms(state.elapsed)}"
    _put_text(grid, top + nh + 2, center_x - len(elapsed) // 2, elapsed, theme.REC)

    # Control hint on the bottom row.
    hint = "[space] pause   [+/-] 10s   [q] quit"
    _put_text(grid, layout.rows - 1, max(0, (layout.cols - len(hint)) // 2),
              hint, theme.HINT)
