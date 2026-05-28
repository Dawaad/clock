import math

import pytest

from clock.view import (
    AUTO_SPEED,
    BASE_PITCH,
    BASE_YAW,
    ORBIT_STEP,
    PITCH_MAX,
    PITCH_MIN,
    ViewState,
    advance_rotation,
    apply_view_key,
)


def test_defaults():
    v = ViewState()
    assert v.pitch == BASE_PITCH
    assert v.yaw == BASE_YAW
    assert v.auto_rotate is True


def test_left_right_change_yaw():
    v = ViewState(auto_rotate=False)
    assert apply_view_key(v, "right").yaw == v.yaw + ORBIT_STEP
    assert apply_view_key(v, "left").yaw == v.yaw - ORBIT_STEP


def test_up_down_change_pitch():
    v = ViewState(pitch=0.8, auto_rotate=False)
    assert apply_view_key(v, "down").pitch == 0.8 + ORBIT_STEP
    assert apply_view_key(v, "up").pitch == 0.8 - ORBIT_STEP


def test_pitch_clamped():
    assert apply_view_key(ViewState(pitch=PITCH_MAX), "down").pitch == PITCH_MAX
    assert apply_view_key(ViewState(pitch=PITCH_MIN), "up").pitch == PITCH_MIN


def test_toggle_auto_rotate():
    v = ViewState(auto_rotate=True)
    assert apply_view_key(v, "r").auto_rotate is False
    assert apply_view_key(apply_view_key(v, "r"), "r").auto_rotate is True


def test_unknown_key_noop():
    v = ViewState()
    assert apply_view_key(v, "z") is v


def test_advance_rotation_spins_when_enabled():
    v = ViewState(yaw=0.0, auto_rotate=True)
    assert advance_rotation(v, 1.0).yaw == pytest.approx(AUTO_SPEED)


def test_advance_rotation_noop_when_disabled():
    v = ViewState(yaw=0.0, auto_rotate=False)
    assert advance_rotation(v, 1.0) is v


def test_yaw_wraps():
    v = ViewState(yaw=math.pi - 0.01, auto_rotate=True)
    out = advance_rotation(v, 1.0)
    assert -math.pi <= out.yaw <= math.pi
