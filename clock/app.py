"""Textual application: drives the clocks, input, and frame refresh.

Timer logic lives in :mod:`clock.state` and all drawing in :mod:`clock.ui`; this
layer only wires real clocks and key events to those pure pieces, so it stays
thin and the logic stays unit-testable.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import Horizontal, VerticalScroll, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from .config import Colors, Config
from .keys import Action, dispatch
from .parse import DurationError, parse_duration
from .state import (
    DEFAULT_STEP,
    Stopwatch,
    View,
    adjust,
    advance,
    focus_next,
    focus_prev,
    new_timer,
    sw_reset,
    sw_tick,
    sw_toggle,
    toggle_pause,
    with_now,
)
from .ui import STACK_MIN_H, active_band, content_min_height, render

DEFAULT_FPS = 10
FINISH_BELLS = 4
FINISH_LINGER = 2.0


class DurationModal(ModalScreen[int | None]):
    """A rofi-style centered prompt for entering a countdown duration.

    Dismisses with the parsed seconds on submit, or ``None`` on cancel.
    """

    # Layout only; colors are applied from the active palette in on_mount so the
    # prompt matches whatever --theme is in effect.
    CSS = """
    DurationModal { align: center middle; }
    #dialog { width: 56; height: auto; padding: 1 2; }
    #prompt { height: 3; }
    #chip { padding: 0 1; margin: 1 2 0 0; text-style: bold; }
    #dur { height: 3; }
    #error { height: 1; }
    #hint { height: 1; }
    """

    BINDINGS = [("escape", "cancel", "cancel")]

    def __init__(self, colors: Colors) -> None:
        super().__init__()
        self._co = colors

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="prompt"):
                yield Label("TIMER", id="chip")
                yield Input(placeholder="e.g. 5m, 30:00, 90s, 1h30m", id="dur")
            yield Label("", id="error")
            yield Label("[enter] start    [esc] cancel", id="hint")

    def on_mount(self) -> None:
        co = self._co
        bg, ink, soft = Color(*co.bg), Color(*co.ink), Color(*co.ink_soft)
        faint, accent = Color(*co.faint), Color(*co.accent)
        # The modal screen's own backdrop defaults to a light surface; theme it
        # so the area around the dialog matches the active palette.
        self.styles.background = bg
        dialog = self.query_one("#dialog")
        dialog.styles.background = bg
        dialog.styles.border = ("round", faint)
        chip = self.query_one("#chip")
        chip.styles.background = accent
        chip.styles.color = bg
        inp = self.query_one("#dur", Input)
        inp.styles.background = bg
        inp.styles.color = ink
        inp.styles.border = ("tall", faint)
        self.query_one("#error", Label).styles.color = accent
        self.query_one("#hint", Label).styles.color = soft
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            total = parse_duration(event.value)
        except DurationError as exc:
            self.query_one("#error", Label).update(str(exc))
            return
        self.dismiss(total)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ClockApp(App):
    CSS = """
    Screen { background: rgb(237,234,226); }
    #scroll { width: 100%; height: 100%; overflow-x: hidden; overflow-y: auto; }
    #frame { width: auto; height: auto; }
    """

    def __init__(
        self,
        total_seconds: int | None,
        *,
        config: Config | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wallclock: Callable[[], datetime] = datetime.now,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__()
        self._cfg = config or Config()
        self._monotonic = monotonic
        self._wallclock = wallclock
        self._fps = fps
        self._last = 0.0
        self._alerted = False
        self._configured = total_seconds is not None
        self.state = new_timer(total_seconds or 0, wallclock())
        self.stopwatch = Stopwatch()
        self.view = View()
        self._keybinds = dict(self._cfg.keybinds)
        self._last_frame: str | None = None
        self._rendered_h = STACK_MIN_H

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll"):
            yield Static(id="frame")

    def on_mount(self) -> None:
        self.screen.styles.background = Color(*self._cfg.colors.bg)
        self._last = self._monotonic()
        self.set_interval(1 / self._fps, self._tick)
        self._draw()

    def _tick(self) -> None:
        now = self._monotonic()
        dt, self._last = now - self._last, now
        # The stopwatch runs independently of whether a countdown is configured.
        self.stopwatch = sw_tick(self.stopwatch, dt)
        if self._configured:
            self.state = advance(self.state, dt)
            if self.state.finished and not self._alerted:
                self._on_finished()
        self.state = with_now(self.state, self._wallclock())
        self._draw()

    def _on_finished(self) -> None:
        self._alerted = True
        for _ in range(FINISH_BELLS):
            self.bell()
        self.set_timer(FINISH_LINGER, self.exit)

    def on_key(self, event) -> None:
        action = dispatch(self.view.active, event.key, self._keybinds)
        if action is not None:
            self._apply(action)

    def _apply(self, action: Action) -> None:
        if action is Action.QUIT:
            self.exit()
            return
        if action is Action.SET_TIMER:
            self._open_picker()
            return
        if action is Action.FOCUS_NEXT:
            self.view = focus_next(self.view)
            self.call_after_refresh(self._scroll_to_focus)
        elif action is Action.FOCUS_PREV:
            self.view = focus_prev(self.view)
            self.call_after_refresh(self._scroll_to_focus)
        elif action is Action.PAUSE:
            self.state = toggle_pause(self.state)
        elif action is Action.ADJUST_UP:
            self.state = adjust(self.state, DEFAULT_STEP)
        elif action is Action.ADJUST_DOWN:
            self.state = adjust(self.state, -DEFAULT_STEP)
        elif action is Action.SW_TOGGLE:
            self.stopwatch = sw_toggle(self.stopwatch)
        elif action is Action.SW_RESET:
            self.stopwatch = sw_reset(self.stopwatch)
        elif action is Action.CLEAR_TIMER:
            self.state = new_timer(0, self._wallclock())
            self._configured = False
            self._alerted = False
        self._draw()

    def _open_picker(self) -> None:
        self.push_screen(DurationModal(self._cfg.colors), self._on_duration_chosen)

    def _scroll_to_focus(self) -> None:
        """Bring the focused section's band into view (no-op when it all fits)."""
        try:
            sc = self.query_one("#scroll", VerticalScroll)
        except NoMatches:
            return
        y0, _ = active_band(self.view.active, self._rendered_h)
        sc.scroll_to(y=y0, animate=False)

    def _on_duration_chosen(self, total: int | None) -> None:
        if total is None:
            # Cancelled: fall back to (or keep) the default blank-timer view.
            return
        self.state = new_timer(total, self._wallclock())
        self._configured = True
        self._alerted = False
        self._last = self._monotonic()
        self._draw()

    def on_resize(self, event) -> None:
        self._draw()

    def _draw(self) -> None:
        # A scheduled interval tick can fire during teardown, after the widget
        # has been unmounted; skip drawing rather than crash.
        if not self.is_running:
            return
        try:
            frame_widget = self.query_one("#frame", Static)
        except NoMatches:
            return
        w, vh = self.size.width, self.size.height
        co = self._cfg.colors
        min_h = content_min_height()
        if min_h > vh:
            # Content is taller than the viewport: render its full height (less
            # one column for the scrollbar) so the container can scroll it.
            self._rendered_h = min_h
            frame = render(self.state, (w - 1, min_h), self.view, self.stopwatch, co)
        else:
            self._rendered_h = vh
            frame = render(self.state, (w, vh), self.view, self.stopwatch, co)

        # Skip the (expensive) ANSI parse + widget update when nothing changed.
        if frame == self._last_frame:
            return
        self._last_frame = frame
        frame_widget.update(Text.from_ansi(frame))


def run(total_seconds: int | None, config: Config | None = None) -> None:
    ClockApp(total_seconds, config=config).run()
