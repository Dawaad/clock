"""Tiny braille canvas for drawing the smooth clock ring.

Dot space is 2x4 per cell. Braille dots are ~square (terminal cells are ~1:2),
so a circle drawn with equal x/y radius in dot space renders round.
"""

from __future__ import annotations

import math

from .raster import Frame
from .theme import RGB

BRAILLE_BASE = 0x2800
_DOT_BITS = {
    (0, 0): 0x01, (1, 0): 0x08,
    (0, 1): 0x02, (1, 1): 0x10,
    (0, 2): 0x04, (1, 2): 0x20,
    (0, 3): 0x40, (1, 3): 0x80,
}


class Canvas:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.dx, self.dy = cols * 2, rows * 4
        self.bits: dict[tuple[int, int], int] = {}
        self.color: dict[tuple[int, int], RGB] = {}

    def dot(self, x: float, y: float, color: RGB) -> None:
        ix, iy = int(round(x)), int(round(y))
        if not (0 <= ix < self.dx and 0 <= iy < self.dy):
            return
        cell = (ix // 2, iy // 4)
        self.bits[cell] = self.bits.get(cell, 0) | _DOT_BITS[(ix % 2, iy % 4)]
        self.color[cell] = color           # last writer wins (arc over track)

    def arc(self, cx: float, cy: float, radius: float, a0: float, a1: float,
            color: RGB, thick: int = 1) -> None:
        """Arc in dot space; a=0 at top, increasing clockwise."""
        span = a1 - a0
        steps = max(2, int(abs(span) / (2 * math.pi) * max(120, radius * 8)))
        for i in range(steps + 1):
            a = a0 + span * i / steps
            for t in range(thick):
                rr = radius - (thick - 1) / 2 + t
                self.dot(cx + rr * math.sin(a), cy - rr * math.cos(a), color)

    def line(self, x0: float, y0: float, x1: float, y1: float, color: RGB) -> None:
        n = max(2, int(math.hypot(x1 - x0, y1 - y0)))
        for i in range(n + 1):
            t = i / n
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, color)

    def blit(self, frame: Frame, x0: int, y0: int, x1: int, y1: int) -> None:
        """Write braille glyphs onto the frame, clipped to a cell rect."""
        for (gx, gy), bits in self.bits.items():
            if x0 <= gx <= x1 and y0 <= gy <= y1:
                frame.put(gx, gy, chr(BRAILLE_BASE + bits), self.color[(gx, gy)])
