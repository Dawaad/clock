from datetime import datetime

import pytest

from clock.app import ClockApp
from clock.config import DEFAULT_KEYBINDS, Config
from clock.keys import Section

T0 = datetime(2026, 5, 28, 14, 33, 0)


def make_app(total=300, monotonic_value=1000.0):
    # Frozen monotonic => dt is 0, so the countdown does not advance on its own
    # and key behaviour can be asserted deterministically.
    return ClockApp(
        total,
        monotonic=lambda: monotonic_value,
        wallclock=lambda: T0,
        fps=60,
    )


@pytest.mark.asyncio
async def test_pause_key_toggles_state():
    app = make_app()
    async with app.run_test() as pilot:
        assert app.state.paused is False
        await pilot.press("space")
        assert app.state.paused is True
        await pilot.press("p")
        assert app.state.paused is False


@pytest.mark.asyncio
async def test_adjust_keys_change_remaining_when_timer_focused():
    app = make_app(total=300)
    async with app.run_test() as pilot:
        assert app.view.active is Section.TIMER
        await pilot.press("plus")
        assert app.state.remaining == 310
        await pilot.press("minus")
        assert app.state.remaining == 300


@pytest.mark.asyncio
async def test_adjust_keys_noop_when_timer_not_focused():
    app = make_app(total=300)
    async with app.run_test() as pilot:
        await pilot.press("down")  # focus STOPWATCH
        assert app.view.active is Section.STOPWATCH
        await pilot.press("plus")
        assert app.state.remaining == 300  # unchanged


@pytest.mark.asyncio
async def test_space_does_not_pause_timer_when_stopwatch_focused():
    app = make_app(total=300)
    async with app.run_test() as pilot:
        await pilot.press("down")  # focus STOPWATCH
        await pilot.press("space")  # toggles stopwatch, not the timer
        assert app.state.paused is False
        assert app.stopwatch.running is True


@pytest.mark.asyncio
async def test_short_viewport_is_scrollable():
    # A short viewport stacks taller than the screen and must scroll.
    app = make_app()
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.query_one("#scroll").max_scroll_y > 0


@pytest.mark.asyncio
async def test_focus_autoscrolls_into_view():
    # Focusing the last section in a short viewport scrolls it into view (4A).
    app = make_app()
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        sc = app.query_one("#scroll")
        assert sc.scroll_offset.y == 0
        await pilot.press("up")  # wrap to the last section (TIME)
        await pilot.pause()
        assert app.view.active is Section.TIME
        assert sc.scroll_offset.y > 0


@pytest.mark.asyncio
async def test_wide_tall_viewport_does_not_scroll():
    app = make_app()
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#scroll").max_scroll_y == 0


@pytest.mark.asyncio
async def test_arrow_keys_navigate_sections():
    app = make_app()
    async with app.run_test() as pilot:
        assert app.view.active is Section.TIMER
        await pilot.press("down")
        assert app.view.active is Section.STOPWATCH
        await pilot.press("down")
        assert app.view.active is Section.TIME
        await pilot.press("down")  # wraps
        assert app.view.active is Section.TIMER
        await pilot.press("up")  # wraps back
        assert app.view.active is Section.TIME


@pytest.mark.asyncio
async def test_rebound_quit_key():
    cfg = Config(keybinds={**DEFAULT_KEYBINDS, "quit": ("x",)})
    app = ClockApp(300, config=cfg, monotonic=lambda: 1000.0, wallclock=lambda: T0, fps=60)
    async with app.run_test() as pilot:
        await pilot.press("q")  # no longer bound to quit
        await pilot.pause()
        assert app.return_code is None
        await pilot.press("x")  # rebound quit
        await pilot.pause()
    assert app.return_code is not None


@pytest.mark.asyncio
async def test_quit_exits_app():
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code is not None


@pytest.mark.asyncio
async def test_tick_after_teardown_is_safe():
    # A queued interval tick firing after the widget is unmounted must not crash.
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
    app._tick()  # post-teardown; should be a no-op, not raise


def make_unconfigured(monotonic_value=1000.0):
    return ClockApp(
        None,
        monotonic=lambda: monotonic_value,
        wallclock=lambda: T0,
        fps=60,
    )


@pytest.mark.asyncio
async def test_no_duration_shows_default_view_without_editor():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.editor.active is False
        assert app._configured is False
        assert app.state.total_seconds == 0


@pytest.mark.asyncio
async def test_set_timer_from_default_view():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app.editor.active
        await pilot.press("5", "m", "enter")
        await pilot.pause()
        assert app._configured
        assert app.state.total_seconds == 300
        assert app.editor.active is False


@pytest.mark.asyncio
async def test_cancel_editor_keeps_default_view():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app.editor.active
        await pilot.press("escape")
        await pilot.pause()
        assert app.editor.active is False
        assert app._configured is False
    assert app.return_code is None


@pytest.mark.asyncio
async def test_editor_invalid_input_shows_error_and_holds():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.press("x", "enter")  # not a valid duration
        await pilot.pause()
        assert app.editor.active  # stays open
        assert app.editor.error is not None
        assert app._configured is False


@pytest.mark.asyncio
async def test_editor_backspace_edits_buffer():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.press("5", "9", "backspace", "m", "enter")
        await pilot.pause()
        assert app.state.total_seconds == 300  # "5m" after backspacing the 9


@pytest.mark.asyncio
async def test_c_key_clears_active_timer():
    app = make_app(total=300)
    async with app.run_test() as pilot:
        assert app._configured
        await pilot.press("c")
        assert app._configured is False
        assert app.state.total_seconds == 0


@pytest.mark.asyncio
async def test_c_key_noop_without_active_timer():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        assert app._configured is False
        assert app.state.total_seconds == 0
    assert app.return_code is None


@pytest.mark.asyncio
async def test_space_toggles_focused_stopwatch():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # focus STOPWATCH
        assert app.view.active is Section.STOPWATCH
        assert app.stopwatch.running is False
        await pilot.press("space")
        assert app.stopwatch.running is True
        await pilot.press("space")
        assert app.stopwatch.running is False


@pytest.mark.asyncio
async def test_stopwatch_counts_up_independently():
    clock = {"t": 1000.0}
    app = ClockApp(None, monotonic=lambda: clock["t"], wallclock=lambda: T0, fps=60)
    async with app.run_test() as pilot:
        await pilot.press("down")  # focus STOPWATCH
        await pilot.press("space")  # start it
        clock["t"] = 1003.0  # 3s elapse with no timer configured
        await pilot.pause()
        assert app.stopwatch.elapsed >= 3.0
        assert app._configured is False


@pytest.mark.asyncio
async def test_c_resets_running_stopwatch_when_focused():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # focus STOPWATCH
        await pilot.press("space")  # start it
        assert app.stopwatch.running
        await pilot.press("c")  # reset, contextual to the stopwatch
        assert app.stopwatch.running is False
        assert app.stopwatch.elapsed == 0.0
    assert app.return_code is None


@pytest.mark.asyncio
async def test_e_key_opens_editor():
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        assert app.editor.active


@pytest.mark.asyncio
async def test_unconfigured_timer_does_not_advance_or_finish():
    clock = {"t": 1000.0}
    app = ClockApp(None, monotonic=lambda: clock["t"], wallclock=lambda: T0, fps=60)
    async with app.run_test() as pilot:
        await pilot.pause()
        clock["t"] = 2000.0  # lots of real time passes while picker is open
        await pilot.pause()
        assert app._alerted is False
        assert app.state.remaining == 0  # held, never went "finished"


@pytest.mark.asyncio
async def test_countdown_advances_with_monotonic():
    clock = {"t": 1000.0}
    app = ClockApp(300, monotonic=lambda: clock["t"], wallclock=lambda: T0, fps=60)
    async with app.run_test() as pilot:
        clock["t"] = 1005.0  # 5 seconds elapse
        await pilot.pause()
        assert app.state.remaining <= 295
