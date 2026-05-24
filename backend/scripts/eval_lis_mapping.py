"""Wrapper: `python scripts/eval_lis_mapping.py` — see training/eval_lis_mapping.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.eval_lis_mapping import main as _main
if __name__ == '__main__':
    _main()
