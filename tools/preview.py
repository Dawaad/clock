"""Dev tool: rasterize a UI frame to a PNG so the output can be eyeballed.

Usage: python tools/preview.py [out.png] [remaining_seconds] [cols] [rows]
"""

import re
import sys
from dataclasses import replace
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from clock.state import new_timer
from clock.ui import render

FONT_PATH = "/usr/share/fonts/TTF/DejaVuSansMono.ttf"
CW, CH = 9, 18  # cell pixel size (~1:2)
ESC = re.compile(r"\033\[([0-9;]*)m")


def parse(line):
    """Yield (char, fg, bg) for each visible cell in an emitted line."""
    fg, bg = (230, 230, 232), (18, 18, 20)
    cells = []
    i = 0
    for m in ESC.finditer(line):
        for ch in line[i:m.start()]:
            cells.append((ch, fg, bg))
        codes = [int(c) for c in m.group(1).split(";") if c != ""]
        j = 0
        while j < len(codes):
            if codes[j] == 38 and codes[j + 1] == 2:
                fg = tuple(codes[j + 2:j + 5]); j += 5
            elif codes[j] == 48 and codes[j + 1] == 2:
                bg = tuple(codes[j + 2:j + 5]); j += 5
            elif codes[j] == 0:
                fg, bg = (230, 230, 232), (18, 18, 20); j += 1
            else:
                j += 1
        i = m.end()
    for ch in line[i:]:
        cells.append((ch, fg, bg))
    return cells


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
    remaining = int(sys.argv[2]) if len(sys.argv) > 2 else 215
    cols = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    rows = int(sys.argv[4]) if len(sys.argv) > 4 else 44

    s = new_timer(max(remaining, 1) + 100, datetime(2026, 5, 28, 14, 33))
    s = replace(s, remaining=float(remaining))

    frame = render(s, (cols, rows))
    lines = frame.split("\n")
    img = Image.new("RGB", (cols * CW, rows * CH), (18, 18, 20))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 16)
    for y, line in enumerate(lines):
        for x, (ch, fg, bg) in enumerate(parse(line)):
            px, py = x * CW, y * CH
            draw.rectangle([px, py, px + CW, py + CH], fill=bg)
            if ch != " ":
                draw.text((px, py - 1), ch, font=font, fill=fg)
    img.save(out)
    print(f"wrote {out} ({cols}x{rows} cells)")


if __name__ == "__main__":
    main()
