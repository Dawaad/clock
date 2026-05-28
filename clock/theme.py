"""Colours, gradient helpers, and size-derived layout geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

RGB = tuple[int, int, int]

# Gradient + chrome colours (truecolor).
RED: RGB = (236, 64, 52)
ORANGE: RGB = (255, 138, 0)
YELLOW: RGB = (255, 208, 32)
TRACK: RGB = (95, 99, 110)
WHITE: RGB = (244, 244, 246)
LABEL: RGB = (120, 124, 138)
HINT: RGB = (90, 94, 104)
HEADER: RGB = (150, 154, 168)
REC: RGB = (236, 64, 52)

# --- 3D puck palette (reference-photo recreation) ---
FACE: RGB = (242, 242, 244)         # white dial face
INK: RGB = (34, 34, 38)             # primary text / ticks
INK_SOFT: RGB = (122, 126, 134)     # secondary labels
ACCENT: RGB = (224, 50, 40)         # red dial indicator / REC dot
BODY: RGB = (126, 130, 136)         # base rim/grille gray
BODY_DARK: RGB = (58, 60, 66)       # shaded rim
BG_LIGHT: RGB = (66, 68, 74)        # backdrop highlight
BG_DARK: RGB = (20, 20, 24)         # backdrop shadow
SHADOW: RGB = (8, 8, 10)            # cast shadow

# Minimum terminal size before we show a "too small" message.
MIN_COLS = 30
MIN_ROWS = 16

# Vertical tick rail (image-3 right rail).
RAIL_TICKS = 21          # number of horizontal ticks in the rail
RAIL_LONG = 5            # long-tick every N
# Radial ticks around the ring.
RADIAL_TICKS = 60


def lerp(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def grad(t: float) -> RGB:
    """Red -> orange -> yellow across t in [0, 1]."""
    if t < 0.5:
        return lerp(RED, ORANGE, t / 0.5)
    return lerp(ORANGE, YELLOW, (t - 0.5) / 0.5)


def dim(c: RGB, f: float) -> RGB:
    return tuple(round(v * f) for v in c)  # type: ignore[return-value]


@dataclass(frozen=True)
class Layout:
    """Geometry derived from terminal cell dimensions.

    Cell space is (cols x rows). The braille canvas doubles columns and
    quadruples rows, so dot space is (2*cols x 4*body_rows).
    """

    cols: int
    rows: int
    too_small: bool
    body_rows: int      # rows reserved for the dial (bottom row is the hint)
    cx: float           # ring centre, dot space
    cy: float
    radius: float       # ring centre-line radius, dot space
    thick: int          # ring thickness in dots
    scale: int          # big-number glyph scale
    rail_col: int       # cell column for the vertical tick rail

    @classmethod
    def from_size(cls, cols: int, rows: int) -> "Layout":
        too_small = cols < MIN_COLS or rows < MIN_ROWS
        body_rows = max(1, rows - 1)
        # Leave room on the right for the vertical rail.
        rail_col = cols - 4
        # Ring occupies the cells left of the rail. Dot space doubles columns,
        # so the horizontal centre of that region in dots is rail_col.
        cx = float(rail_col)
        cy = body_rows * 2      # dot-space y centre (body_rows * 4 / 2)
        radius = max(4.0, min(rail_col, body_rows * 2) - 3)
        thick = max(2, int(radius) // 18)
        scale = min(3, max(1, round(radius / 42)))
        return cls(
            cols=cols,
            rows=rows,
            too_small=too_small,
            body_rows=body_rows,
            cx=cx,
            cy=cy,
            radius=radius,
            thick=thick,
            scale=scale,
            rail_col=rail_col,
        )


def angle_point(cx: float, cy: float, r: float, a: float) -> tuple[float, float]:
    """Point on a circle. a=0 is at the top, increasing clockwise."""
    return cx + r * math.sin(a), cy - r * math.cos(a)
