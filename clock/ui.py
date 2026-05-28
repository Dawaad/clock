"""Focus-driven stacked-section UI.

Three full-width sections stack vertically, each in its own titled box with a
keybind strip at its top; the focused section is drawn in the accent colour. A
single global-hint footer sits at the bottom.

    +== TIMER  ◀ ============================+   <- focused (accent border)
    | space pause   + +10s   - -10s   c clear |   <- section keybind strip
    |  00:32:00                  ( ring )      |
    +-- STOPWATCH ----------------------------+
    | space start / pause   c reset            |
    |  00:01:12                                |
    +-- TIME ---------------------------------+
    |  14:33                     ( analog )    |
    |  Thursday, 28th of May                   |
    +-----------------------------------------+
      ↑↓ navigate   e set timer   q quit          <- global footer

``render(state, size, view, stopwatch, colors)`` is deterministic given inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import theme
from .braille import Canvas
from .config import Colors
from .font import compose_number
from .keys import Action, Section, global_binds, primary_glyph, section_binds
from .parse import format_hms, format_readout
from .raster import Frame
from .state import Editor, Stopwatch, TimerState, View

_DEFAULT_COLORS = Colors()
_DEFAULT_VIEW = View()

EIGHTHS = "▁▂▃▄▅▆▇█"

# Minimum inner width before a section drops its side-by-side clock and shows
# the textual readout alone.
SIDE_BY_SIDE_W = 48


@dataclass(frozen=True)
class RowSpec:
    min_h: int
    flex: int = 0


# Two stacked rows: TIMER on top (full width), then a bottom row split into
# TIME (left 2/3) and STOPWATCH (right 1/3). Both rows flex to absorb height.
ROW_SPECS: tuple[RowSpec, ...] = (
    RowSpec(min_h=12, flex=1),  # TIMER row
    RowSpec(min_h=12, flex=1),  # TIME | STOPWATCH row
)
FOOTER_H = 1

# Fraction of the width the TIME column takes in the bottom row.
TIME_FRACTION = 2 / 3

# Smallest frame that shows every section at its natural height; the app renders
# at least this tall and scrolls when the viewport is shorter.
STACK_MIN_H = sum(r.min_h for r in ROW_SPECS) + FOOTER_H


def content_min_height() -> int:
    return STACK_MIN_H


def distribute(specs: tuple[RowSpec, ...], avail: int) -> list[int]:
    """Heights per row that sum to ``avail`` (flex absorbs the slack).

    When ``avail`` is at most the combined minimum, return the minimums as-is so
    the caller can scroll the overflow. Slack is split across flex rows by
    largest-remainder so the heights are integers and sum exactly.
    """
    base = [s.min_h for s in specs]
    total_min = sum(base)
    if avail <= total_min:
        return base
    slack = avail - total_min
    total_flex = sum(s.flex for s in specs)
    if total_flex == 0:
        base[-1] += slack
        return base
    shares = [slack * s.flex / total_flex for s in specs]
    floors = [int(x) for x in shares]
    rem = slack - sum(floors)
    # Hand the leftover units to the largest fractional remainders (flex
    # rows sort first; zero-flex rows have remainder 0).
    order = sorted(
        range(len(specs)),
        key=lambda i: (shares[i] - floors[i], specs[i].flex),
        reverse=True,
    )
    for i in order[:rem]:
        floors[i] += 1
    return [b + f for b, f in zip(base, floors)]


def _row_heights(rows: int) -> tuple[int, int]:
    """(timer-row height, bottom-row height) for the section area."""
    avail = max(0, rows - FOOTER_H)
    th, bh = distribute(ROW_SPECS, avail)
    return th, bh


def section_rects(cols: int, rows: int) -> list[tuple[Section, int, int, int, int]]:
    """(section, x0, y0, x1, y1) rects: TIMER on top, TIME | STOPWATCH below."""
    th, bh = _row_heights(rows)
    by0, by1 = th, th + bh - 1
    split = int(cols * TIME_FRACTION)
    return [
        (Section.TIMER, 0, 0, cols - 1, th - 1),
        (Section.TIME, 0, by0, split - 1, by1),
        (Section.STOPWATCH, split, by0, cols - 1, by1),
    ]


def active_band(active: Section, rows: int) -> tuple[int, int]:
    """Vertical (y0, y1) band of the row the active section lives in."""
    th, bh = _row_heights(rows)
    if active is Section.TIMER:
        return 0, th - 1
    return th, th + bh - 1


def render(
    state: TimerState,
    size: tuple[int, int],
    view: View | None = None,
    stopwatch: Stopwatch | None = None,
    colors: Colors | None = None,
    editor: Editor | None = None,
) -> str:
    cols, rows = size
    co = colors if colors is not None else _DEFAULT_COLORS
    if cols < theme.MIN_COLS or rows < theme.MIN_ROWS:
        return _too_small(cols, rows, co)

    vw = view if view is not None else _DEFAULT_VIEW
    sw = stopwatch if stopwatch is not None else Stopwatch()
    f = Frame(cols, rows)
    f.fill_bg(co.bg)

    drawers = {
        Section.TIMER: lambda r: _timer_content(f, state, *r, co),
        Section.STOPWATCH: lambda r: _stopwatch_content(f, sw, *r, co),
        Section.TIME: lambda r: _time_content(f, state, *r, cols, rows, co),
    }
    rects = section_rects(cols, rows)
    for section, x0, y0, x1, y1 in rects:
        active = section is vw.active
        inner = _section(f, x0, y0, x1, y1, section, active, state, sw, co)
        drawers[section](inner)

    if editor is not None and editor.active:
        tx0, ty0, tx1, ty1 = next(r[1:] for r in rects if r[0] is Section.TIMER)
        _editor_box(f, tx0, ty0, tx1, ty1, editor, co)

    _footer(f, cols, rows, co)
    return f.emit()


# --------------------------------------------------------------------------- #
# Section chrome (border + title + keybind strip + focus highlight)
# --------------------------------------------------------------------------- #

_TITLES = {
    Section.TIMER: "TIMER",
    Section.STOPWATCH: "STOPWATCH",
    Section.TIME: "TIME",
}


def _section(f, x0, y0, x1, y1, section, active, state, sw, co) -> tuple[int, int, int, int]:
    """Draw a section box and its keybind strip; return the inner content rect."""
    border = co.accent if active else co.faint
    _box(f, x0, y0, x1, y1, border)

    title = _TITLES[section]
    tcolor = co.accent if active else co.ink_soft
    tx = x0 + 2
    f.text(tx, y0, f" {title} ", tcolor)
    if active:
        f.text(tx + len(title) + 3, y0, "◀", co.accent)

    _keybind_strip(f, x0 + 2, y0 + 1, x1 - 2, section, state, sw, co)
    return x0 + 2, y0 + 2, x1 - 2, y1 - 1


def _keybind_strip(f, x0, y, x1, section, state, sw, co) -> None:
    """Render a section's contextual keys as ``glyph label`` tokens."""
    x = x0
    for key_glyph, label in _strip_entries(section, state, sw):
        token = f"{key_glyph} {label}"
        if x + len(token) > x1:
            break
        f.text(x, y, key_glyph, co.ink)
        f.text(x + len(key_glyph) + 1, y, label, co.ink_soft)
        x += len(token) + 3


def _strip_entries(section, state, sw) -> list[tuple[str, str]]:
    """(glyph, label) pairs for a section, honouring stateful availability.

    ADJUST_UP/DOWN collapse into one ``+/-`` token; clear/reset only show when
    there is something to clear.
    """
    entries: list[tuple[str, str]] = []
    for b in section_binds(section):
        if b.action is Action.ADJUST_DOWN:
            continue  # folded into the ADJUST_UP token below
        if b.action is Action.ADJUST_UP:
            entries.append(("+/-", "adjust 10s"))
            continue
        if b.action is Action.CLEAR_TIMER and state.total_seconds <= 0:
            continue
        if b.action is Action.SW_RESET and not (sw.running or sw.elapsed > 0):
            continue
        entries.append((primary_glyph(b.keys), b.label))
    return entries


def _editor_box(f, rx0, ry0, rx1, ry1, editor, co) -> None:
    """Inline duration prompt anchored to the TIMER section's bottom-right."""
    bw = min(40, rx1 - rx0 - 1)
    body = ["input", "hint"] + (["error"] if editor.error else [])
    bh = len(body) + 2  # content rows + top/bottom border
    x1, y1 = rx1 - 2, ry1 - 1
    x0, y0 = max(rx0 + 2, x1 - bw + 1), max(ry0 + 2, y1 - bh + 1)

    # Clear the area (it overlaps the ring) and draw an accent-bordered box.
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            f.put(x, y, " ", co.ink, co.bg)
    _box(f, x0, y0, x1, y1, co.accent)
    f.text(x0 + 2, y0, " SET TIMER ", co.accent)

    iw = x1 - x0 - 3
    f.put(x0 + 2, y0 + 1, ">", co.ink_soft)
    if editor.buffer:
        f.text(x0 + 4, y0 + 1, (editor.buffer + "_")[:iw], co.ink)
    else:
        f.text(x0 + 4, y0 + 1, "e.g. 5m, 30:00, 1h30m"[:iw], co.faint)
    f.text(x0 + 2, y0 + 2, "enter start   esc cancel"[:iw], co.ink_soft)
    if editor.error:
        f.text(x0 + 2, y0 + 3, editor.error[:iw], co.accent)


def _footer(f, cols, rows, co) -> None:
    # The two focus binds collapse into one nav hint; the rest show as tokens.
    parts = ["↑↓ navigate"]
    for b in global_binds():
        if b.action in (Action.FOCUS_NEXT, Action.FOCUS_PREV):
            continue
        parts.append(f"{primary_glyph(b.keys)} {b.label}")
    line = "   ".join(parts)
    f.text(max(0, (cols - len(line)) // 2), rows - 1, line[:cols], co.ink_soft)


# --------------------------------------------------------------------------- #
# Section content
# --------------------------------------------------------------------------- #

def _timer_content(f, state, ax0, ay0, ax1, ay1, co) -> None:
    w = ax1 - ax0 + 1
    if w >= SIDE_BY_SIDE_W:
        split = ax0 + int(w * 0.62)
        _timer_readout(f, state, ax0, ay0, split - 2, ay1, co)
        _ring(f, state, split, ay0, ax1, ay1, co)
    else:
        _timer_readout(f, state, ax0, ay0, ax1, ay1, co)


def _timer_readout(f, state, ax0, ay0, ax1, ay1, co) -> None:
    w = ax1 - ax0 + 1
    status = "PAUSED" if state.paused else "RUNNING"
    f.text(ax1 - len(status) + 1, ay0, status, co.accent if state.paused else co.ink_soft)
    by = ay1
    f.text(ax0, by - 1, "ELAPSED", co.ink_soft)
    f.text(ax1 - 8, by - 1, format_hms(state.elapsed), co.ink_soft)
    elapsed_frac = 1.0 - state.fraction
    for i in range(w):
        h = 3.5 + 3.3 * math.sin(i * 0.9) * math.cos(i * 0.37 + 0.5)
        idx = max(0, min(7, int(h)))
        color = co.ink if (i / max(1, w - 1)) <= elapsed_frac else co.faint
        f.put(ax0 + i, by, EIGHTHS[idx], color)
    _readout(f, ax0, ay0, by - 2, w, format_readout(state.remaining), co.ink)


def _stopwatch_content(f, sw, ax0, ay0, ax1, ay1, co) -> None:
    w = ax1 - ax0 + 1
    if sw.running:
        status, color = "RUNNING", co.ink_soft
    elif sw.elapsed > 0:
        status, color = "PAUSED", co.accent
    else:
        status, color = "READY", co.faint
    f.text(ax1 - len(status) + 1, ay0, status, color)
    _readout(f, ax0, ay0, ay1, w, format_readout(sw.elapsed), co.ink)


def _time_content(f, state, ax0, ay0, ax1, ay1, cols, rows, co) -> None:
    w = ax1 - ax0 + 1
    now = state.now
    year = now.strftime("%Y")
    f.text(ax1 - len(year) - 1, ay0, f"[{year}]", co.ink_soft)
    date = f"{now.strftime('%A')}, {_ordinal(now.day)} of {now.strftime('%B')}"
    f.text(ax0, ay1, date[:w], co.ink_soft)

    if w >= SIDE_BY_SIDE_W:
        split = ax0 + int(w * 0.55)
        _readout(f, ax0, ay0, ay1 - 1, split - ax0, now.strftime("%H:%M"), co.ink)
        _analog(f, split, ay0, ax1, ay1 - 1, now, cols, rows, co)
    else:
        _readout(f, ax0, ay0, ay1 - 1, w, now.strftime("%H:%M"), co.ink)


# --------------------------------------------------------------------------- #
# Braille clocks
# --------------------------------------------------------------------------- #

def _ring(f, state, ax0, ay0, ax1, ay1, co) -> None:
    pct = f"{round(state.fraction * 100)}%"
    f.text(ax1 - len(pct) + 1, ay0, pct, co.ink_soft)
    cx, cy = (ax0 + ax1) // 2, (ay0 + ay1) // 2
    avail_w, avail_h = ax1 - ax0 + 1, ay1 - ay0 + 1
    radius = min(avail_w, 2 * avail_h) * 0.84
    if radius < 4:
        return
    cxd, cyd = cx * 2 + 1, cy * 4 + 2
    canvas = Canvas(f.cols, f.rows)
    canvas.arc(cxd, cyd, radius, 0, 2 * math.pi, co.faint, thick=1)
    frac = state.fraction
    if frac > 0:
        canvas.arc(cxd, cyd, radius, 0, 2 * math.pi * frac, co.ink, thick=2)
    a = 2 * math.pi * frac
    ex, ey = cxd + radius * 0.9 * math.sin(a), cyd - radius * 0.9 * math.cos(a)
    canvas.line(cxd, cyd, ex, ey, co.ink)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        canvas.dot(ex + dx, ey + dy, co.ink)
    canvas.blit(f, ax0, ay0, ax1, ay1)


def _analog(f, ax0, ay0, ax1, ay1, now, cols, rows, co) -> None:
    """Reflective analog clock for the wall time (hands jump per second)."""
    cx, cy = (ax0 + ax1) // 2, (ay0 + ay1) // 2
    avail_w, avail_h = ax1 - ax0 + 1, ay1 - ay0 + 1
    radius = min(avail_w, 2 * avail_h) * 0.84
    if radius < 4:
        return
    cxd, cyd = cx * 2 + 1, cy * 4 + 2
    canvas = Canvas(f.cols, f.rows)
    canvas.arc(cxd, cyd, radius, 0, 2 * math.pi, co.faint, thick=1)
    for h in range(12):
        a = 2 * math.pi * h / 12
        r0, r1 = radius * 0.84, radius
        canvas.line(
            cxd + r0 * math.sin(a), cyd - r0 * math.cos(a),
            cxd + r1 * math.sin(a), cyd - r1 * math.cos(a), co.ink_soft,
        )
    hour, minute, second = now.hour % 12, now.minute, now.second
    a_h = 2 * math.pi * ((hour + minute / 60) / 12)
    a_m = 2 * math.pi * (minute / 60)
    a_s = 2 * math.pi * (second / 60)
    _hand(canvas, cxd, cyd, a_h, radius * 0.5, co.ink)
    _hand(canvas, cxd, cyd, a_m, radius * 0.78, co.ink)
    _hand(canvas, cxd, cyd, a_s, radius * 0.9, co.accent)
    canvas.blit(f, ax0, ay0, ax1, ay1)


def _hand(canvas, cxd, cyd, angle, length, color) -> None:
    canvas.line(cxd, cyd, cxd + length * math.sin(angle), cyd - length * math.cos(angle), color)


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #

def _box(f, x0, y0, x1, y1, c) -> None:
    for x in range(x0, x1 + 1):
        f.put(x, y0, "─", c)
        f.put(x, y1, "─", c)
    for y in range(y0, y1 + 1):
        f.put(x0, y, "│", c)
        f.put(x1, y, "│", c)
    f.put(x0, y0, "┌", c)
    f.put(x1, y0, "┐", c)
    f.put(x0, y1, "└", c)
    f.put(x1, y1, "┘", c)


def _readout(f, x, top, bottom, w, text, color) -> None:
    """Big block readout within [top, bottom].

    Tries normal kerning first, then a tight (no-gap) variant so narrow columns
    (e.g. the 1/3-width stopwatch) keep the block font instead of dropping to
    plain text; plain text is the last resort when even tight won't fit.
    """
    region_h = bottom - top + 1
    for gap in (1, 0):
        glyph_rows = compose_number(text, 1, gap)
        nh, nw = len(glyph_rows), max(len(r) for r in glyph_rows)
        if region_h >= nh and nw <= w:
            ty = top + (region_h - nh) // 2
            for r, line in enumerate(glyph_rows):
                for col, ch in enumerate(line):
                    if ch == "#":
                        f.put(x + col, ty + r, "█", color)
            return
    f.text(x, top + max(0, region_h // 2), text[:w], color)


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _too_small(cols, rows, co) -> str:
    f = Frame(cols, rows)
    f.fill_bg(co.bg)
    msg = "WINDOW TOO SMALL"
    f.text(max(0, (cols - len(msg)) // 2), rows // 2, msg[:cols], co.ink_soft)
    return f.emit()
