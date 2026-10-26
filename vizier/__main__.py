"""Allow ``python -m vizier`` to launch the CLI/GUI."""
from __future__ import annotations

from vizier.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
