"""Sanity tests for the top-level package."""
from __future__ import annotations

import vizier
from vizier.__version__ import __codename__, __version__


def test_version_is_set() -> None:
    assert __version__
    assert "." in __version__
    assert __codename__ == "Royal Advisor"


def test_public_exports() -> None:
    for name in vizier.__all__:
        assert hasattr(vizier, name), name
