"""
Wrapper: `python scripts/build_golden_set.py`

Builds per-language golden sets at project_root/golden_set/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.build_golden import main as _main

if __name__ == '__main__':
    if not any(a.startswith('--out') for a in sys.argv[1:]):
        sys.argv.extend(['--out', str(Path(__file__).resolve().parents[2] / 'golden_set')])
    _main()
