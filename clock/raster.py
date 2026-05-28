"""A flat cell frame with per-cell foreground + background truecolor.

Each cell holds a char, an fg colour and a bg colour. ``emit`` coalesces runs of
identical (fg, bg) so the escape stream stays small.
"""

from __future__ import annotations

from .theme import BG, INK, RGB

DEFAULT_FG: RGB = INK
DEFAULT_BG: RGB = BG


class Frame:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.char = [[" "] * cols for _ in range(rows)]
        self.fg: list[list[RGB | None]] = [[None] * cols for _ in range(rows)]
        self.bg: list[list[RGB | None]] = [[None] * cols for _ in range(rows)]

    def _in(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def set_bg(self, x: int, y: int, color: RGB) -> None:
        if self._in(x, y):
            self.bg[y][x] = color

    def fill_bg(self, color: RGB) -> None:
        for y in range(self.rows):
            row = self.bg[y]
            for x in range(self.cols):
                row[x] = color

    def put(self, x: int, y: int, char: str, fg: RGB, bg: RGB | None = None) -> None:
        if not self._in(x, y):
            return
        self.char[y][x] = char
        self.fg[y][x] = fg
        if bg is not None:
            self.bg[y][x] = bg

    def text(self, x: int, y: int, s: str, fg: RGB) -> None:
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, fg)

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
