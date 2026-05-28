"""Immutable timer state and pure transitions.

The state is a frozen snapshot; transitions return new instances so they are
trivial to unit-test. The app layer owns the real clocks and feeds them in:

- ``advance(state, dt)`` moves the countdown by a monotonic delta.
- ``with_now(state, now)`` stamps the current wall time (used by the header).
- ``apply_key(state, key)`` handles pause / adjust controls.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

# Arrow keys are reserved for orbiting the camera (see clock.view), so timer
# adjustment uses the +/- pair only.
PAUSE_KEYS = frozenset({" ", "p"})
ADD_KEYS = frozenset({"+", "="})
SUB_KEYS = frozenset({"-", "_"})

DEFAULT_STEP = 10


@dataclass(frozen=True)
class TimerState:
    total_seconds: int          # denominator for the progress fraction
    remaining: float            # seconds left
    now: datetime               # current wall time (for the header)
    paused: bool = False

    @property
    def finished(self) -> bool:
        return self.remaining <= 0

    @property
    def elapsed(self) -> float:
        return max(0.0, self.total_seconds - self.remaining)

    @property
    def fraction(self) -> float:
        """Portion of time remaining, clamped to [0, 1]."""
        if self.total_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining / self.total_seconds))


def new_timer(total_seconds: int, now: datetime) -> TimerState:
    return TimerState(
        total_seconds=total_seconds,
        remaining=float(total_seconds),
        now=now,
    )


def advance(state: TimerState, dt: float) -> TimerState:
    """Move the countdown forward by ``dt`` seconds of real time."""
    if state.paused or state.finished or dt <= 0:
        return state
    return replace(state, remaining=max(0.0, state.remaining - dt))


def with_now(state: TimerState, now: datetime) -> TimerState:
    return replace(state, now=now)


def apply_key(state: TimerState, key: str, step: int = DEFAULT_STEP) -> TimerState:
    """Apply a control key. Unknown keys leave the state unchanged."""
    if key in PAUSE_KEYS:
        return replace(state, paused=not state.paused)
    if key in ADD_KEYS:
        remaining = state.remaining + step
        return replace(
            state,
            remaining=remaining,
            total_seconds=max(state.total_seconds, int(round(remaining))),
        )
    if key in SUB_KEYS:
        return replace(state, remaining=max(0.0, state.remaining - step))
    return state
