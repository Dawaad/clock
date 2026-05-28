"""A small z-buffered cell frame with foreground + background truecolor.

Each cell holds a char, an fg colour, a bg colour and a depth. Surfaces are
written with a depth test (nearest wins); overlays (text, line art) are written
on top but still respect occlusion via the depth they pass in. ``emit``
coalesces runs of identical (fg, bg) to keep the escape stream small.
"""

from __future__ import annotations

import math

from .theme import RGB

DEFAULT_FG: RGB = (230, 230, 232)
DEFAULT_BG: RGB = (18, 18, 20)
_EPS = 1e-6


class Frame:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.char = [[" "] * cols for _ in range(rows)]
        self.fg: list[list[RGB | None]] = [[None] * cols for _ in range(rows)]
        self.bg: list[list[RGB | None]] = [[None] * cols for _ in range(rows)]
        self.z = [[math.inf] * cols for _ in range(rows)]

    def _in(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def set_bg(self, x: int, y: int, color: RGB) -> None:
        """Unconditional background paint (used for the backdrop)."""
        if self._in(x, y):
            self.bg[y][x] = color

    def surface(
        self,
        x: int,
        y: int,
        depth: float,
        *,
        bg: RGB | None = None,
        fg: RGB | None = None,
        char: str | None = None,
    ) -> None:
        """Depth-tested surface write (nearest wins)."""
        if not self._in(x, y) or depth > self.z[y][x] + _EPS:
            return
        self.z[y][x] = depth
        if bg is not None:
            self.bg[y][x] = bg
        if fg is not None:
            self.fg[y][x] = fg
        if char is not None:
            self.char[y][x] = char

    def overlay(self, x: int, y: int, depth: float, char: str, fg: RGB) -> None:
        """Draw a glyph on top of a surface, respecting occlusion.

        Passes if the overlay is no farther than what already occupies the
        cell, so UI on the face is hidden where a nearer rim covers it.
        """
        if not self._in(x, y) or depth > self.z[y][x] + 0.5:
            return
        self.char[y][x] = char
        self.fg[y][x] = fg

    def emit(self) -> str:
        out: list[str] = []
        for y in range(self.rows):
            parts: list[str] = []
            last: tuple[RGB, RGB] | None = None
            row_char, row_fg, row_bg = self.char[y], self.fg[y], self.bg[y]
            for x in range(self.cols):
                fg = row_fg[x] or DEFAULT_FG
                bg = row_bg[x] or DEFAULT_BG
                if (fg, bg) != last:
                    parts.append(
                        f"\033[38;2;{fg[0]};{fg[1]};{fg[2]}"
                        f";48;2;{bg[0]};{bg[1]};{bg[2]}m"
                    )
                    last = (fg, bg)
                parts.append(row_char[x])
            parts.append("\033[0m")
            out.append("".join(parts))
        return "\n".join(out)
