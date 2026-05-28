import pytest

from clock.parse import (
    DurationError,
    format_hms,
    format_readout,
    parse_duration,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("30", 30),
        ("  30  ", 30),
        ("1", 1),
        ("5s", 5),
        ("5m", 300),
        ("10h", 36000),
        ("1h", 3600),
        ("2h", 7200),
        ("2.5h", 9000),
        ("0.5m", 30),
        ("1h30m", 5400),
        ("1m30s", 90),
        ("1h2m3s", 3723),
        ("90S", 90),
        ("30:00", 1800),
        ("0:30", 30),
        ("90:00", 5400),  # mm:ss allows minutes > 59
        ("1:00:00", 3600),
        ("1:02:03", 3723),
        ("2.5", 2),  # bare fractional seconds, rounded
        ("2.4", 2),
    ],
)
def test_valid_durations(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "-5",
        "0",
        "0s",
        "0:00",
        "1:2:3:4",
        "1:99",       # seconds field out of range (mm:ss)
        "1:60:00",    # minutes field out of range (h:mm:ss)
        "1:00:99",    # seconds field out of range (h:mm:ss)
        "5x",         # unknown unit
        "5m3",        # trailing junk after units
        "1.5:00",     # decimals not allowed in colon form
        "h",          # unit without value
    ],
)
def test_invalid_durations(text):
    with pytest.raises(DurationError):
        parse_duration(text)


def test_none_raises():
    with pytest.raises(DurationError):
        parse_duration(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0:00.0"),
        (1.0, "0:01.0"),
        (5.5, "0:05.5"),
        (4.999, "0:04.9"),  # floored tenths
        (59, "0:59.0"),
        (60, "1:00.0"),
        (90, "1:30.0"),
        (599, "9:59.0"),
        (3600, "1:00:00.0"),
        (3661, "1:01:01.0"),
        (36000, "10:00:00.0"),
    ],
)
def test_format_readout(seconds, expected):
    assert format_readout(seconds) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "00:00:00"),
        (5, "00:00:05"),
        (65, "00:01:05"),
        (3661, "01:01:01"),
        (4963, "01:22:43"),
    ],
)
def test_format_hms(seconds, expected):
    assert format_hms(seconds) == expected
