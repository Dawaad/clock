"""Duration parsing and time formatting.

Accepted input forms (case-insensitive, surrounding whitespace ignored):

    30          bare number of seconds
    5s 5m 10h   single unit suffix
    1h30m       combined unit suffixes (fractional allowed: 2.5h)
    30:00       mm:ss
    1:00:00     h:mm:ss

Colon forms are integer-only. In h:mm:ss the minute/second fields must be
0-59; in mm:ss the second field must be 0-59 (minutes may exceed 59).
"""

from __future__ import annotations

import math
import re

_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([hms])")
_BARE_RE = re.compile(r"^\d+(?:\.\d+)?$")


class DurationError(ValueError):
    """Raised when a duration string cannot be parsed."""


def parse_duration(text: str) -> int:
    """Parse a duration string into a positive whole number of seconds.

    Raises DurationError with a human-readable message on invalid input.
    """
    if text is None:
        raise DurationError("no duration given")
    raw = text.strip().lower()
    if not raw:
        raise DurationError("no duration given")

    if ":" in raw:
        seconds = _parse_colon(raw)
    elif _BARE_RE.match(raw):
        seconds = float(raw)
    elif any(u in raw for u in _UNIT_SECONDS):
        seconds = _parse_units(raw)
    else:
        raise DurationError(f"could not understand duration {text!r}")

    total = int(round(seconds))
    if total <= 0:
        raise DurationError("duration must be positive")
    return total


def _parse_colon(raw: str) -> int:
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise DurationError(f"expected mm:ss or h:mm:ss, got {raw!r}")
    if not all(p.isdigit() for p in parts):
        raise DurationError(f"colon form must use whole numbers: {raw!r}")
    nums = [int(p) for p in parts]
    if len(parts) == 2:
        minutes, secs = nums
        if secs > 59:
            raise DurationError("seconds field must be 0-59")
        return minutes * 60 + secs
    hours, minutes, secs = nums
    if minutes > 59 or secs > 59:
        raise DurationError("minutes and seconds fields must be 0-59")
    return hours * 3600 + minutes * 60 + secs


def _parse_units(raw: str) -> float:
    # Reject stray characters that are not part of a recognised unit token.
    if _UNIT_RE.sub("", raw).strip():
        raise DurationError(f"could not understand duration {raw!r}")
    matches = _UNIT_RE.findall(raw)
    if not matches:
        raise DurationError(f"could not understand duration {raw!r}")
    return sum(float(value) * _UNIT_SECONDS[unit] for value, unit in matches)


def format_readout(remaining: float) -> str:
    """Adaptive big readout: seconds, m:ss, or h:mm:ss."""
    secs = max(0, int(math.ceil(remaining - 1e-9)))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    if secs >= 60:
        return f"{m}:{s:02d}"
    return str(s)


def format_hms(seconds: float) -> str:
    """Zero-padded HH:MM:SS (used for the elapsed indicator)."""
    secs = max(0, int(seconds))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
