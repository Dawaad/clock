"""Camera orientation state and its pure transitions.

Separate from :class:`~clock.state.TimerState`: this is purely how the puck is
viewed, not the countdown itself. Arrow keys orbit; ``r`` toggles a slow
auto-rotation about the vertical axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# Default framing, tuned to approximate the reference photo.
BASE_PITCH = 0.95           # ~54 deg tilt back
BASE_YAW = -0.42            # ~-24 deg, dial scale toward the right
PITCH_MIN, PITCH_MAX = 0.05, 1.40
ORBIT_STEP = math.radians(6)
AUTO_SPEED = 0.35           # rad/s when auto-rotating

ORBIT_KEYS = {"left", "right", "up", "down"}
TOGGLE_KEY = "r"


@dataclass(frozen=True)
class ViewState:
    pitch: float = BASE_PITCH
    yaw: float = BASE_YAW
    auto_rotate: bool = True


def apply_view_key(view: ViewState, key: str) -> ViewState:
    if key == "left":
        return replace(view, yaw=view.yaw - ORBIT_STEP)
    if key == "right":
        return replace(view, yaw=view.yaw + ORBIT_STEP)
    if key == "up":
        return replace(view, pitch=_clamp_pitch(view.pitch - ORBIT_STEP))
    if key == "down":
        return replace(view, pitch=_clamp_pitch(view.pitch + ORBIT_STEP))
    if key == TOGGLE_KEY:
        return replace(view, auto_rotate=not view.auto_rotate)
    return view


def advance_rotation(view: ViewState, dt: float) -> ViewState:
    if not view.auto_rotate or dt <= 0:
        return view
    return replace(view, yaw=_wrap(view.yaw + AUTO_SPEED * dt))


def _clamp_pitch(p: float) -> float:
    return max(PITCH_MIN, min(PITCH_MAX, p))


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
