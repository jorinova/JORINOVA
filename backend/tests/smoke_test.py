import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)

def test_health_check():
    """Verify the health check endpoint returns 200 OK."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_login_page():
    """Verify the login page (HTML) is served."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_unauthorized_access():
    """Verify that protected endpoints return 401/403 without a token."""
    # Patient list endpoint (prefix in main.py is /api/v1, prefix in router is /patients)
    # So full path is /api/v1/patients/
    response = client.get("/api/v1/patients/")
    assert response.status_code in [401, 403, 405]

def test_ai_nexus_dispatch():
    """Verify the AI Nexus dispatch endpoint exists."""
    # /api/v1/ai/dispatch
    response = client.post("/api/v1/ai/dispatch", json={})
    # Should be 401 (if protected) or 422 (if payload invalid)
    assert response.status_code in [401, 422]
