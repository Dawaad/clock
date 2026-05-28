from datetime import datetime

import pytest

from clock.app import ClockApp, DurationModal
from clock.config import DEFAULT_KEYBINDS, Config

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
async def test_adjust_keys_change_remaining():
    app = make_app(total=300)
    async with app.run_test() as pilot:
        await pilot.press("plus")
        assert app.state.remaining == 310
        await pilot.press("minus")
        assert app.state.remaining == 300


@pytest.mark.asyncio
async def test_narrow_viewport_is_scrollable():
    # A narrow, short viewport stacks taller than the screen and must scroll.
    app = make_app()
    async with app.run_test(size=(48, 20)) as pilot:
        await pilot.pause()
        sc = app.query_one("#scroll")
        assert sc.max_scroll_y > 0
        await pilot.press("end")
        await pilot.pause()
        assert sc.scroll_offset.y > 0


@pytest.mark.asyncio
async def test_wide_viewport_does_not_scroll():
    app = make_app()
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#scroll").max_scroll_y == 0


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
async def test_no_duration_opens_picker_and_sets_timer():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DurationModal)
        await pilot.press("5", "m", "enter")
        await pilot.pause()
        assert app._configured
        assert app.state.total_seconds == 300
        assert not isinstance(app.screen, DurationModal)


@pytest.mark.asyncio
async def test_cancel_picker_with_no_timer_exits():
    app = make_unconfigured()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.return_code is not None


@pytest.mark.asyncio
async def test_e_key_opens_picker():
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, DurationModal)


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
