from datetime import datetime

import pytest

from clock.app import ClockApp

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


@pytest.mark.asyncio
async def test_countdown_advances_with_monotonic():
    clock = {"t": 1000.0}
    app = ClockApp(300, monotonic=lambda: clock["t"], wallclock=lambda: T0, fps=60)
    async with app.run_test() as pilot:
        clock["t"] = 1005.0  # 5 seconds elapse
        await pilot.pause()
        assert app.state.remaining <= 295
