"""Command-line entry point: ``clock <duration>``."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .app import run
from .parse import DurationError, parse_duration

_EXAMPLES = (
    "examples: 30  5s  5m  2.5h  1h30m  30:00  1:00:00\n"
    "controls: [space] pause   [+/-] adjust 10s   [q] quit"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clock",
        description="A clean four-panel terminal countdown timer.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "duration",
        help="how long to count down (seconds, unit suffixes, or mm:ss / h:mm:ss)",
    )
    parser.add_argument("--version", action="version", version=f"clock {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        total = parse_duration(args.duration)
    except DurationError as exc:
        parser.error(str(exc))  # prints usage + message, exits 2

    if not sys.stdout.isatty():
        print("clock: requires an interactive terminal", file=sys.stderr)
        return 1

    run(total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
