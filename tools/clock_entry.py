"""PyInstaller entry point: a thin script wrapper around the console entry.

PyInstaller bundles a script file (not a module), so this re-exposes
``clock.cli:main`` as a runnable script for the frozen binary.
"""

import sys

from clock.cli import main

if __name__ == "__main__":
    sys.exit(main())
