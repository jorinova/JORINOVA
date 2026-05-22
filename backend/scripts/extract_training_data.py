"""
Wrapper: `python scripts/extract_training_data.py`

Thin entry-point that calls into the training package. Default output is
`./datasets/` (project root) per the runbook convention.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.extract import main as _main

if __name__ == '__main__':
    # If the caller didn't pass --out, default to ../datasets
    if not any(a.startswith('--out') for a in sys.argv[1:]):
        sys.argv.extend(['--out', str(Path(__file__).resolve().parents[2] / 'datasets')])
    _main()
