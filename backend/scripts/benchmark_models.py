"""Wrapper: `python scripts/benchmark_models.py` — see training/benchmark_models.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.benchmark_models import main as _main
if __name__ == '__main__':
    _main()
