"""Compatibility shim for python-decouple.

The project expects:
    from decouple import config, Csv

But the environment may not have `python-decouple` installed (or may have
a conflicting `decouple` package). This file provides minimal drop-in
implementations for the subset we use.

It reads values from environment variables and returns defaults.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional


def config(key: str, default: Optional[Any] = None, cast: Optional[Callable[[str], Any]] = None) -> Any:
    """Read from environment with optional type casting."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    if cast is None:
        return val
    try:
        return cast(val)
    except Exception:
        # Fallback: return raw value if cast fails
        return val


class Csv:
    """Cast a comma-separated string into a list of strings."""

    def __call__(self, value: str) -> list[str]:
        if value is None:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

