"""Flat editorial palette (cream paper, dark ink) for the panel UI."""

from __future__ import annotations

RGB = tuple[int, int, int]

BG: RGB = (237, 234, 226)       # warm cream paper
INK: RGB = (30, 30, 32)         # near-black primary text
INK_SOFT: RGB = (138, 136, 130) # secondary labels / captions
FAINT: RGB = (203, 200, 192)    # borders, tracks, unfilled bars
ACCENT: RGB = (198, 72, 56)     # muted red status accent

# Minimum terminal size before the "too small" message.
MIN_COLS = 24
MIN_ROWS = 10
