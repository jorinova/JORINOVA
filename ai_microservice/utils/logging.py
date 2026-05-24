"""Minimal logging helper. Mirrors the main app's logger naming convention."""
from __future__ import annotations

import logging
import sys


_initialised = False


def _init() -> None:
    global _initialised
    if _initialised:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s :: %(message)s',
    ))
    root = logging.getLogger('jorinova.ai')
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(handler)
    _initialised = True


def get_logger(name: str) -> logging.Logger:
    _init()
    return logging.getLogger(f'jorinova.ai.{name}')
