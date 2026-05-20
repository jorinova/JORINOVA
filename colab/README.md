# JORINOVA NEXUS ALIS-X — Google Colab Setup

Run this notebook to bootstrap the ALIS-X backend environment inside Google Colab / Kaggle / Jupyter.

## One-click open

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jorinova/JORINOVA.git)

> Opens the `colab/` directory as a Colab notebook workspace directly from GitHub.

---

## What this does

1. Clones the `jorinova/JORINOVA` repo into the Colab VM
2. Installs backend dependencies from `requirements.txt`
3. Initialises deterministic RNG state
4. Runs the database migration + seed
5. Leaves you at `backend/` ready to `uvicorn` or run further cells

---

## Manual cell-by-cell

```python
# ─── CELL 1: Clone repo ────────────────────────────────────────────────
!git clone https://github.com/jorinova/JORINOVA.git /content/JORINOVA
%cd /content/JORINOVA/backend
```

```python
# ─── CELL 2: Install dependencies ─────────────────────────────────────
!pip install -q -r requirements.txt
```

```python
# ─── CELL 3: Determinism + DB ──────────────────────────────────────────
from core.determinism import initialize_determinism
initialize_determinism()
print('Deterministic state initialised.')

import subprocess, sys
result = subprocess.run([sys.executable, 'scripts/migrate.py'],
                       capture_output=True, text=True)
print(result.stdout[-2000:])   # last 2 k of log
if result.returncode != 0:
    print('STDERR:', result.stderr[-1000:])
```

```python
# ─── CELL 4: Start API (background) ───────────────────────────────────
import subprocess
api = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app',
     '--host', '0.0.0.0', '--port', '8000'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
import time; time.sleep(3)
print('API PID:', api.pid)
print('Health:', subprocess.run(['curl', '-s', 'http://localhost:8000/api/v1/health'],
                                capture_output=True, text=True).stdout)
```

```python
# ─── CELL 5: Test endpoint ─────────────────────────────────────────────
!curl -s http://localhost:8000/api/v1/health | python -m json.tool
```
