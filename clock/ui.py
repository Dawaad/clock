"""Flat four-quadrant panel UI (editorial 'player' aesthetic).

    +----------------------+----------------------+
    | TIMER                | KEYBINDS             |
    |  00:32:00            |  space  pause        |
    |  ▇▅▃▆█▄▂ ...          |  + / -  adjust       |
    +----------------------+----------------------+
    | CLOCK   (ring)       | TIME                 |
    |     .-''-.           |  14:33               |
    |    (  ()  )          |  Thu 28th of May     |
    +----------------------+----------------------+

render(state, size) -> ANSI string. Deterministic given its inputs.
"""

from __future__ import annotations

import math

from . import theme
from .braille import Canvas
from .font import compose_number
from .parse import format_hms, format_readout
from .raster import Frame
from .state import Stopwatch, TimerState

EIGHTHS = "▁▂▃▄▅▆▇█"

# (key, full description, short description for narrow columns)
KEYBINDS = [
    ("space", "pause / resume", "pause"),
    ("+  /  -", "adjust 10s", "+-10s"),
    ("e", "set timer", "set"),
    ("s", "stopwatch", "stopw"),
    ("q", "quit", "quit"),
]
# Shown only while a timer is active (see _keybinds_quadrant).
CLEAR_BIND = ("c", "clear", "clear")


def _keybinds_for(state: TimerState) -> list[tuple[str, str, str]]:
    binds = list(KEYBINDS)
    if state.total_seconds > 0:
        binds.insert(-1, CLEAR_BIND)
    return binds


# Below this width the grid collapses to a single scrollable column. Set so the
# three bottom thirds (the widest header is STOPWATCH) stay legible in the grid.
NARROW_W = 88
# Stacked band heights (the clock band flexes to fill remaining space).
STACK_TIMER_H = 11
STACK_KEY_H = 14
STACK_TIME_H = 11
# Tall enough for the 7-row block readout (header + glyph), matching TIME.
STACK_STOPWATCH_H = 11
STACK_CLOCK_MIN = 10
# Minimum total height of the stacked layout (clock at its minimum).
STACK_MIN_H = (
    1 + STACK_TIMER_H + 1 + STACK_KEY_H + 1 + STACK_CLOCK_MIN
    + 1 + STACK_TIME_H + 1 + STACK_STOPWATCH_H + 1
)


def is_narrow(cols: int) -> bool:
    return cols < NARROW_W


def render(state: TimerState, size: tuple[int, int], stopwatch: Stopwatch | None = None) -> str:
    cols, rows = size
    if cols < theme.MIN_COLS or rows < theme.MIN_ROWS:
        return _too_small(cols, rows)

    sw = stopwatch if stopwatch is not None else Stopwatch()
    f = Frame(cols, rows)
    f.fill_bg(theme.BG)
    if is_narrow(cols):
        _render_stacked(f, state, sw, cols, rows)
    else:
        _render_grid(f, state, sw, cols, rows)
    return f.emit()


def _render_grid(f, state, sw, cols, rows) -> None:
    x0, y0, x1, y1 = 1, 1, cols - 2, rows - 2
    span_x = x1 - x0
    # Top row: wide timer panel + narrower keybinds. Bottom row: equal thirds.
    top_split = x0 + max(14, round(0.62 * span_x))
    bot_split1 = x0 + round(span_x / 3)
    bot_split2 = x0 + round(2 * span_x / 3)
    midy = y0 + round(0.46 * (y1 - y0))     # top row a touch shorter
    _frame_box(f, x0, y0, x1, y1, top_split, (bot_split1, bot_split2), midy)

    _timer_quadrant(f, state, x0 + 2, y0 + 1, top_split - 2, midy - 1)
    _keybinds_quadrant(f, state, top_split + 2, y0 + 1, x1 - 2, midy - 1)
    _clock_quadrant(f, state, x0 + 2, midy + 1, bot_split1 - 2, y1 - 1, cols, rows)
    _time_quadrant(f, state, bot_split1 + 2, midy + 1, bot_split2 - 2, y1 - 1)
    _stopwatch_quadrant(f, sw, bot_split2 + 2, midy + 1, x1 - 2, y1 - 1)


def _render_stacked(f, state, sw, cols, rows) -> None:
    """Single-column layout: panels stacked, clock flexes to fill height.

    Rendered into ``rows`` (which the app sets to at least STACK_MIN_H), so when
    the viewport is shorter the app scrolls this taller frame.
    """
    x0, y0, x1, y1 = 1, 1, cols - 2, rows - 2
    _outer_box(f, x0, y0, x1, y1)

    timer_top = y0 + 1
    timer_bot = timer_top + STACK_TIMER_H - 1
    sep1 = timer_bot + 1
    key_top = sep1 + 1
    key_bot = key_top + STACK_KEY_H - 1
    sep2 = key_bot + 1
    sw_bot = y1 - 1
    sw_top = sw_bot - STACK_STOPWATCH_H + 1
    sep4 = sw_top - 1
    time_bot = sep4 - 1
    time_top = time_bot - STACK_TIME_H + 1
    sep3 = time_top - 1
    clock_top = sep2 + 1
    clock_bot = sep3 - 1

    for sep in (sep1, sep2, sep3, sep4):
        for x in range(x0, x1 + 1):
            f.put(x, sep, "─", theme.FAINT)
        f.put(x0, sep, "├", theme.FAINT)
        f.put(x1, sep, "┤", theme.FAINT)

    ix0, ix1 = x0 + 2, x1 - 2
    _timer_quadrant(f, state, ix0, timer_top, ix1, timer_bot)
    _keybinds_quadrant(f, state, ix0, key_top, ix1, key_bot)
    _clock_quadrant(f, state, ix0, clock_top, ix1, clock_bot, cols, rows)
    _time_quadrant(f, state, ix0, time_top, ix1, time_bot)
    _stopwatch_quadrant(f, sw, ix0, sw_top, ix1, sw_bot)


# --------------------------------------------------------------------------- #
# Quadrants
# --------------------------------------------------------------------------- #

def _timer_quadrant(f, state, ax0, ay0, ax1, ay1) -> None:
    w = ax1 - ax0 + 1
    _header(f, ax0, ay0, "TIMER")
    status = "PAUSED" if state.paused else "RUNNING"
    f.text(ax1 - len(status) + 1, ay0, status,
           theme.ACCENT if state.paused else theme.INK_SOFT)

    # Bottom two rows: elapsed label + equalizer bar.
    by = ay1
    f.text(ax0, by - 1, "ELAPSED", theme.INK_SOFT)
    f.text(ax1 - 8, by - 1, format_hms(state.elapsed), theme.INK_SOFT)
    elapsed_frac = 1.0 - state.fraction
    for i in range(w):
        h = 3.5 + 3.3 * math.sin(i * 0.9) * math.cos(i * 0.37 + 0.5)
        idx = max(0, min(7, int(h)))
        color = theme.INK if (i / max(1, w - 1)) <= elapsed_frac else theme.FAINT
        f.put(ax0 + i, by, EIGHTHS[idx], color)

    _readout(f, ax0, ay0 + 2, by - 2, w, format_readout(state.remaining), theme.INK)


def _time_quadrant(f, state, ax0, ay0, ax1, ay1) -> None:
    w = ax1 - ax0 + 1
    now = state.now
    _header(f, ax0, ay0, "TIME")
    year = now.strftime("%Y")
    f.text(ax1 - len(year) - 1, ay0, f"[{year}]", theme.INK_SOFT)

    date = f"{now.strftime('%A')}, {_ordinal(now.day)} of {now.strftime('%B')}"
    f.text(ax0, ay1, date[:w], theme.INK_SOFT)

    _readout(f, ax0, ay0 + 2, ay1 - 2, w, now.strftime("%H:%M"), theme.INK)


def _stopwatch_quadrant(f, sw, ax0, ay0, ax1, ay1) -> None:
    w = ax1 - ax0 + 1
    _header(f, ax0, ay0, "STOPWATCH")
    if sw.running:
        status, color = "RUNNING", theme.INK_SOFT
    elif sw.elapsed > 0:
        status, color = "PAUSED", theme.ACCENT
    else:
        status, color = "READY", theme.FAINT
    f.text(ax1 - len(status) + 1, ay0, status, color)
    _readout(f, ax0, ay0 + 2, ay1, w, format_readout(sw.elapsed), theme.INK)


def _keybinds_quadrant(f, state, ax0, ay0, ax1, ay1) -> None:
    _header(f, ax0, ay0, "KEYBINDS")
    w = ax1 - ax0 + 1
    narrow = w < 26
    desc_x = ax0 + (8 if narrow else 10)
    y = ay0 + 2
    for key, full, short in _keybinds_for(state):
        f.text(ax0, y, key, theme.INK)
        f.text(desc_x, y, short if narrow else full, theme.INK_SOFT)
        y += 2
        if y > ay1:
            break


def _clock_quadrant(f, state, ax0, ay0, ax1, ay1, cols, rows) -> None:
    _header(f, ax0, ay0, "CLOCK")
    pct = f"{round(state.fraction * 100)}%"
    f.text(ax1 - len(pct) + 1, ay0, pct, theme.INK_SOFT)

    inner_top = ay0 + 1
    avail_w, avail_h = ax1 - ax0 + 1, ay1 - inner_top + 1
    cx = (ax0 + ax1) // 2
    cy = (inner_top + ay1) // 2
    # Fill the panel: horizontal diameter is ~radius cells, vertical ~radius/2.
    radius = min(avail_w, 2 * avail_h) * 0.84
    if radius < 4:
        return
    cxd, cyd = cx * 2 + 1, cy * 4 + 2

    canvas = Canvas(cols, rows)
    canvas.arc(cxd, cyd, radius, 0, 2 * math.pi, theme.FAINT, thick=1)
    frac = state.fraction
    if frac > 0:
        canvas.arc(cxd, cyd, radius, 0, 2 * math.pi * frac, theme.INK, thick=2)
    # Dial pointer to the end of the remaining arc, with a tip dot.
    a = 2 * math.pi * frac
    ex, ey = cxd + radius * 0.9 * math.sin(a), cyd - radius * 0.9 * math.cos(a)
    canvas.line(cxd, cyd, ex, ey, theme.INK)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        canvas.dot(ex + dx, ey + dy, theme.INK)
    canvas.blit(f, ax0, inner_top, ax1, ay1)


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #

def _frame_box(f, x0, y0, x1, y1, top_split, bot_splits, midy) -> None:
    c = theme.FAINT
    for x in range(x0, x1 + 1):
        f.put(x, y0, "─", c)
        f.put(x, y1, "─", c)
        f.put(x, midy, "─", c)
    for y in range(y0, y1 + 1):
        f.put(x0, y, "│", c)
        f.put(x1, y, "│", c)
    for y in range(y0, midy + 1):           # top-row divider
        f.put(top_split, y, "│", c)
    for bs in bot_splits:                    # bottom-row dividers
        for y in range(midy, y1 + 1):
            f.put(bs, y, "│", c)
    f.put(x0, y0, "┌", c)
    f.put(x1, y0, "┐", c)
    f.put(x0, y1, "└", c)
    f.put(x1, y1, "┘", c)
    f.put(x0, midy, "├", c)
    f.put(x1, midy, "┤", c)
    f.put(top_split, y0, "┬", c)
    for bs in bot_splits:
        f.put(bs, y1, "┴", c)
    # Junctions where dividers meet the middle rule: above only -> ┴, below
    # only -> ┬, both -> ┼.
    above, below = {top_split}, set(bot_splits)
    for x in above | below:
        if x in above and x in below:
            ch = "┼"
        elif x in above:
            ch = "┴"
        else:
            ch = "┬"
        f.put(x, midy, ch, c)


def _outer_box(f, x0, y0, x1, y1) -> None:
    c = theme.FAINT
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


def _header(f, x, y, text) -> None:
    f.text(x, y, " ".join(text), theme.INK_SOFT)


def _readout(f, x, top, bottom, w, text, color) -> None:
    """Big block readout within [top, bottom]; plain text when it won't fit."""
    glyph = compose_number(text, 1)
    nh, nw = len(glyph), max(len(r) for r in glyph)
    region_h = bottom - top + 1
    if region_h >= nh and nw <= w:
        ty = top + (region_h - nh) // 2
        for r, line in enumerate(glyph):
            for col, ch in enumerate(line):
                if ch == "#":
                    f.put(x + col, ty + r, "█", color)
    else:
        f.text(x, top + max(0, region_h // 2), text[:w], color)


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _too_small(cols, rows) -> str:
    f = Frame(cols, rows)
    f.fill_bg(theme.BG)
    msg = "WINDOW TOO SMALL"
    f.text(max(0, (cols - len(msg)) // 2), rows // 2, msg[:cols], theme.INK_SOFT)
    return f.emit()
