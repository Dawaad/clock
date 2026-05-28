"""Braille dot canvas and reusable stroke primitives.

The canvas accumulates coloured dots in a 2x4-per-cell braille grid. Where
multiple draws land on the same cell, colours from the highest layer are
averaged so overlapping strokes blend rather than fight.
"""

from __future__ import annotations

import math
from typing import Callable, Union

from .theme import RGB, angle_point

ColorSpec = Union[RGB, Callable[[float], RGB]]

BRAILLE_BASE = 0x2800
_DOT_BITS = {
    (0, 0): 0x01, (1, 0): 0x08,
    (0, 1): 0x02, (1, 1): 0x10,
    (0, 2): 0x04, (1, 2): 0x20,
    (0, 3): 0x40, (1, 3): 0x80,
}


def _resolve(color: ColorSpec, t: float) -> RGB:
    return color(t) if callable(color) else color


class Canvas:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.dx, self.dy = cols * 2, rows * 4
        self.bits: dict[tuple[int, int], int] = {}
        self.csum: dict[tuple[int, int], list[int]] = {}
        self.layer: dict[tuple[int, int], int] = {}

    def dot(self, x: float, y: float, color: RGB, layer: int = 0) -> None:
        ix, iy = int(round(x)), int(round(y))
        if not (0 <= ix < self.dx and 0 <= iy < self.dy):
            return
        cell = (ix // 2, iy // 4)
        self.bits[cell] = self.bits.get(cell, 0) | _DOT_BITS[(ix % 2, iy % 4)]
        cur = self.layer.get(cell, -1)
        if layer > cur:
            self.csum[cell] = [0, 0, 0, 0]
            self.layer[cell] = cur = layer
        if layer == cur:
            s = self.csum[cell]
            s[0] += color[0]
            s[1] += color[1]
            s[2] += color[2]
            s[3] += 1

    def clone(self) -> "Canvas":
        """Copy of the canvas; lets a cached static layer be reused per frame."""
        other = Canvas(self.cols, self.rows)
        other.bits = dict(self.bits)
        other.layer = dict(self.layer)
        other.csum = {k: v[:] for k, v in self.csum.items()}
        return other

    def blit_into(self, grid: list) -> None:
        """Write accumulated braille cells into a cell grid in place."""
        for (gx, gy), bits in self.bits.items():
            if 0 <= gy < len(grid) and 0 <= gx < len(grid[gy]):
                s = self.csum[(gx, gy)]
                color = (s[0] // s[3], s[1] // s[3], s[2] // s[3])
                grid[gy][gx] = (chr(BRAILLE_BASE + bits), color)


def draw_arc(
    canvas: Canvas,
    cx: float,
    cy: float,
    radius: float,
    thick: int,
    a0: float,
    a1: float,
    color: ColorSpec,
    layer: int = 0,
    steps: int | None = None,
) -> None:
    """Stroke a circular arc from angle a0 to a1 (radians, top=0, clockwise)."""
    span = a1 - a0
    if steps is None:
        full = max(120, int(radius * 8))
        steps = max(2, int(abs(span) / (2 * math.pi) * full))
    for i in range(steps):
        t = i / max(1, steps - 1)
        a = a0 + span * t
        col = _resolve(color, t)
        for r in range(thick):
            rr = radius - thick / 2 + r
            x, y = angle_point(cx, cy, rr, a)
            canvas.dot(x, y, col, layer)


def radial_ticks(
    canvas: Canvas,
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    count: int,
    color: ColorSpec,
    layer: int = 0,
) -> None:
    """Short radial tick marks evenly spaced around the full circle.

    ``color`` may be a callable receiving each tick's fraction around the
    circle (0 at top, increasing clockwise).
    """
    span_r = max(1e-6, r_outer - r_inner)
    n = max(2, int(round(span_r)) + 1)
    for k in range(count):
        t = k / count
        a = 2 * math.pi * t
        col = _resolve(color, t)
        for j in range(n):
            rr = r_inner + span_r * j / (n - 1)
            x, y = angle_point(cx, cy, rr, a)
            canvas.dot(x, y, col, layer)


def vertical_ticks(
    canvas: Canvas,
    x_right: float,
    y0: float,
    y1: float,
    count: int,
    long_every: int,
    short_len: int,
    long_len: int,
    color: ColorSpec,
    layer: int = 0,
) -> None:
    """A vertical rail of left-extending horizontal ticks (image-3 dial).

    Ticks are placed top (y0) to bottom (y1); ``color`` may be a callable
    receiving each tick's fraction down the rail.
    """
    for k in range(count):
        t = k / max(1, count - 1)
        y = y0 + (y1 - y0) * t
        length = long_len if k % long_every == 0 else short_len
        col = _resolve(color, t)
        for dxi in range(length):
            canvas.dot(x_right - dxi, y, col, layer)


def emit_grid(grid: list) -> str:
    """Render a cell grid to an ANSI string, coalescing same-colour runs."""
    out: list[str] = []
    for row in grid:
        parts: list[str] = []
        last: RGB | None = None
        for cell in row:
            if cell is None:
                if last is not None:
                    parts.append("\033[0m")
                    last = None
                parts.append(" ")
                continue
            ch, color = cell
            if color != last:
                parts.append(f"\033[38;2;{color[0]};{color[1]};{color[2]}m")
                last = color
            parts.append(ch)
        if last is not None:
            parts.append("\033[0m")
        out.append("".join(parts))
    return "\n".join(out)
