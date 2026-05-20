"""
JORINOVA NEXUS ALIS-X — Google Colab / Kaggle Environment Setup
=================================================================
Run this as the very first cell in any new Colab notebook to bring up
a fully-seeded, deterministic ALIS-X backend environment.

Usage in Colab:
    %run colab/lisis_x_colab_setup.py

Or execute as a notebook: open colab/lisis_x_colab_setup.ipynb
"""

# ── 0. Imports ─────────────────────────────────────────────────────────────────
import subprocess
import sys
import os
import time
from pathlib import Path

# ── 1. Colab-specific housekeeping ────────────────────────────────────────────
def _is_colab() -> bool:
    """Return True when running inside Google Colab."""
    try:
        import google.colab  # noqa: F401 — just probe availability
        return True
    except ImportError:
        return False


# ── 2. Clone repo (idempotent) ────────────────────────────────────────────────
_COLAB_ROOT  = Path('/content/JORINOVA')
_BACKEND_DIR = _COLAB_ROOT / 'backend'
_REPO_URL    = 'https://github.com/jorinova/JORINOVA.git'

def _clone_repo() -> None:
    if _COLAB_ROOT.exists():
        print(f'[colab] Repo already present at {_COLAB_ROOT}')
        return
    print('[colab] Cloning jorinova/JORINOVA …')
    r = subprocess.run(
        ['git', 'clone', '--depth=1', _REPO_URL, str(_COLAB_ROOT)],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print('[colab] Clone complete.')
    else:
        print(f'[colab] Clone failed:\n{r.stderr}')
        raise RuntimeError('Repository clone failed')


# ── 3. Install dependencies ───────────────────────────────────────────────────
def _install_deps() -> None:
    req = _BACKEND_DIR / 'requirements.txt'
    if not req.exists():
        raise FileNotFoundError(f'requirements.txt not found at {req}')
    print('[colab] Installing dependencies …')
    r = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-q', '-r', str(req)],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print('[colab] Dependencies installed.')
    else:
        print(f'[colab] pip warnings:\n{r.stderr[-500:]}')


# ── 4. Ensure backend is on sys.path ─────────────────────────────────────────
def _add_backend_to_path() -> None:
    sys.path.insert(0, str(_BACKEND_DIR))
    print(f'[colab] sys.path[0] = {str(_BACKEND_DIR)}')


# ── 5. Determinism ────────────────────────────────────────────────────────────
def _init_determinism() -> None:
    from core.determinism import initialize_determinism
    initialize_determinism()
    print('[colab] Deterministic RNG initialised (GLOBAL_SEED=42).')


# ── 6. Run migrations + seed ──────────────────────────────────────────────────
def _migrate() -> None:
    migrate_script = _BACKEND_DIR / 'scripts' / 'migrate.py'
    print('[colab] Running database migration + seed …')
    env = os.environ.copy()
    # Point SQLite to Colab scratch space when no PostgreSQL is available
    env.setdefault('DB_ENGINE', 'sqlite')
    r = subprocess.run(
        [sys.executable, str(migrate_script)],
        capture_output=True, text=True,
        cwd=str(_BACKEND_DIR),
        env=env,
    )
    print(r.stdout[-3000:])   # last 3 k of log
    if r.returncode != 0:
        print(f'[colab] Migration STDOUT:\n{r.stdout[-2000:]}')
        print(f'[colab] Migration STDERR:\n{r.stderr[-1000:]}')
        raise RuntimeError('Migration failed — see logs above.')
    print('[colab] Migration complete.')


# ── 7. Start API in background ────────────────────────────────────────────────
def _start_api(port: int = 8000, host: str = '0.0.0.0') -> subprocess.Popen:
    print(f'[colab] Starting FastAPI on {host}:{port} …')
    api_proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app',
         '--host', host, '--port', str(port), '--log-level', 'warning'],
        cwd=str(_BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(4)   # give uvicorn a moment to bind
    rc = api_proc.poll()
    if rc is not None:
        out, err = api_proc.communicate()
        print(f'[colab] API process exited immediately (rc={rc})')
        print(err.decode()[-2000:])
        raise RuntimeError('API failed to start.')
    print(f'[colab] API running — PID {api_proc.pid}.')
    return api_proc


# ── 8. Health probe ───────────────────────────────────────────────────────────
def _health_check(port: int = 8000) -> bool:
    import urllib.request
    try:
        resp = urllib.request.urlopen(f'http://localhost:{port}/api/v1/health', timeout=5)
        body = resp.read().decode()
        print(f'[colab] Health check: {body.strip()}')
        return True
    except Exception as exc:
        print(f'[colab] Health check failed: {exc}')
        return False


# ── 9. Summary ────────────────────────────────────────────────────────────────
def _print_summary() -> None:
    print("""
╔═════════════════════════════════════════════════╗
║  ALIS-X Colab Environment — Ready               ║
╠═════════════════════════════════════════════════╣
║  API      http://localhost:8000                  ║
║  Health   http://localhost:8000/api/v1/health    ║
║  Docs     http://localhost:8000/api/docs          ║
║  Login    admin / Admin@2026 (super_admin)       ║
╚═════════════════════════════════════════════════╝
""")


# ── Entry point ───────────────────────────────────────────────────────────────
def setup_colab(port: int = 8000, auto_start_api: bool = True) -> subprocess.Popen | None:
    """
    Full Colab environment bootstrap.

    Parameters
    ----------
    port: int
        Port for the Uvicorn dev server (default 8000).
    auto_start_api: bool
        Start the API automatically after migration (default True).
        Set False to manage the server manually (e.g. with gunicorn).

    Returns
    -------
    subprocess.Popen or None
        Handle to the running API process when *auto_start_api* is True, else None.
    """
    if not _is_colab():
        print('[colab] Warning: not detected as a Colab runtime.')
        print('[colab] Continuing anyway — suitable for any Linux/macOS/WSL VM.')

    _clone_repo()
    os.chdir(str(_BACKEND_DIR))
    _install_deps()
    _add_backend_to_path()
    _init_determinism()
    _migrate()

    api_proc = None
    if auto_start_api:
        api_proc = _start_api(port=port)
        _health_check(port=port)

    _print_summary()
    return api_proc


# ── Run immediately when executed as a script ─────────────────────────────────
if __name__ == '__main__':
    setup_colab()
