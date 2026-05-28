import re
from dataclasses import replace
from datetime import datetime

from clock.keys import Section
from clock.state import Stopwatch, View, new_timer
from clock.ui import (
    SECTION_SPECS,
    STACK_MIN_H,
    distribute,
    render,
    section_bands,
)

T0 = datetime(2026, 5, 28, 14, 33, 0)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
WIDE = (110, 40)


def strip(s: str) -> str:
    return ANSI.sub("", s)


def state(total=300, remaining=None, paused=False, now=T0):
    s = new_timer(total, now)
    return replace(
        s,
        remaining=float(total if remaining is None else remaining),
        paused=paused,
    )


def line_with(out: str, needle: str) -> int:
    plain = strip(out).split("\n")
    for i, row in enumerate(plain):
        if needle in row:
            return i
    return -1


# --------------------------------------------------------------------------- #
# Layout distributor (10A)
# --------------------------------------------------------------------------- #

def test_distribute_sums_to_avail():
    for avail in range(STACK_MIN_H, STACK_MIN_H + 40):
        heights = distribute(SECTION_SPECS, avail - 1)  # minus footer
        assert sum(heights) == avail - 1


def test_distribute_returns_minimums_on_overflow():
    base = [s.min_h for s in SECTION_SPECS]
    assert distribute(SECTION_SPECS, 1) == base
    assert distribute(SECTION_SPECS, sum(base)) == base


def test_distribute_gives_slack_to_flex_sections():
    base = [s.min_h for s in SECTION_SPECS]
    heights = distribute(SECTION_SPECS, sum(base) + 10)
    # STOPWATCH has flex 0, so its height is unchanged; flex sections grew.
    assert heights[1] == base[1]
    assert heights[0] > base[0] and heights[2] > base[2]


def test_distribute_no_flex_dumps_slack_on_last():
    specs = tuple(replace(s, flex=0) for s in SECTION_SPECS)
    base = [s.min_h for s in specs]
    heights = distribute(specs, sum(base) + 7)
    assert heights[:-1] == base[:-1]
    assert heights[-1] == base[-1] + 7


def test_section_bands_are_contiguous_and_ordered():
    bands = section_bands(40)
    assert [b[0] for b in bands] == [s.section for s in SECTION_SPECS]
    for (_, _, y1), (_, y0_next, _) in zip(bands, bands[1:]):
        assert y0_next == y1 + 1


# --------------------------------------------------------------------------- #
# Rendering contract (9A migration)
# --------------------------------------------------------------------------- #

def test_output_has_one_line_per_row():
    assert len(render(state(), WIDE).split("\n")) == 40


def test_too_small_message():
    assert "WINDOW TOO SMALL" in strip(render(state(), (20, 8)))


def test_section_headers_present_and_no_keybinds_panel():
    out = strip(render(state(), WIDE))
    for header in ("TIMER", "STOPWATCH", "TIME"):
        assert header in out
    assert "KEYBINDS" not in out


def test_timer_keybind_strip():
    out = strip(render(state(), WIDE))
    assert "pause" in out
    assert "adjust 10s" in out


def test_stopwatch_keybind_strip():
    out = strip(render(state(), WIDE, View(active=Section.STOPWATCH)))
    assert "start / pause" in out


def test_global_hints_in_footer():
    out = strip(render(state(), WIDE))
    footer = out.split("\n")[-1]
    assert "navigate" in footer
    assert "set timer" in footer
    assert "quit" in footer


def test_clear_shown_only_with_active_timer():
    active = strip(render(state(total=300), WIDE))
    assert "clear" in active
    blank = strip(render(state(total=0, remaining=0), WIDE))
    assert "clear" not in blank


def test_reset_shown_only_when_stopwatch_used():
    v = View(active=Section.STOPWATCH)
    used = strip(render(state(), WIDE, v, Stopwatch(elapsed=5.0, running=True)))
    assert "reset" in used
    idle = strip(render(state(), WIDE, v, Stopwatch()))
    assert "reset" not in idle


def test_stopwatch_status_reflects_running():
    running = strip(render(state(), WIDE, View(active=Section.STOPWATCH),
                           Stopwatch(elapsed=1.0, running=True)))
    assert "RUNNING" in running
    ready = strip(render(state(), WIDE, stopwatch=Stopwatch()))
    assert "READY" in ready


def test_timer_status_reflects_pause():
    assert "PAUSED" in strip(render(state(paused=True), WIDE))
    assert "RUNNING" in strip(render(state(paused=False), WIDE))


def test_wall_time_and_date_shown():
    out = strip(render(state(now=T0), WIDE))
    assert "28th of May" in out
    assert "Thursday" in out
    assert "[2026]" in out


def test_ring_percentage_shown():
    out = strip(render(state(total=300, remaining=150), WIDE))
    assert "50%" in out


def test_cream_background_emitted():
    assert "48;2;237;234;226" in render(state(), WIDE)


def test_custom_colors_change_background():
    from clock.config import Colors

    co = Colors(bg=(16, 16, 18))
    assert "48;2;16;16;18" in render(state(), WIDE, colors=co)


def test_is_deterministic():
    s, size = state(), (90, 36)
    assert render(s, size) == render(s, size)


def test_renders_at_min_height_without_error():
    out = render(state(total=190, remaining=90), (96, STACK_MIN_H))
    assert len(out.split("\n")) == STACK_MIN_H
    assert "ELAPSED" in strip(out)


# --------------------------------------------------------------------------- #
# Focus highlight + analog clock (12A)
# --------------------------------------------------------------------------- #

def test_focus_marker_moves_with_active_section():
    out_timer = render(state(), WIDE, View(active=Section.TIMER))
    assert strip(out_timer).count("◀") == 1
    # The marker sits on the active section's title row.
    assert line_with(out_timer, "◀") == line_with(out_timer, " TIMER ")

    out_time = render(state(), WIDE, View(active=Section.TIME))
    assert line_with(out_time, "◀") == line_with(out_time, " TIME ")


def test_analog_clock_is_deterministic():
    s = state(now=T0)
    assert render(s, WIDE) == render(s, WIDE)


def test_analog_clock_differs_across_times():
    a = render(state(now=datetime(2026, 5, 28, 14, 33, 7)), WIDE)
    b = render(state(now=datetime(2026, 5, 28, 9, 15, 45)), WIDE)
    assert a != b


def test_analog_clock_identical_within_same_second():
    # Sub-second differences must not change the frame (14A: hands jump/second).
    a = render(state(now=datetime(2026, 5, 28, 14, 33, 7, 100_000)), WIDE)
    b = render(state(now=datetime(2026, 5, 28, 14, 33, 7, 900_000)), WIDE)
    assert a == b
