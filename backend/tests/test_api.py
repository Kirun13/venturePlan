from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_legacy_route_is_retired():
    assert client.post("/plans/generate", json={}).status_code == 410

def test_jobs_require_authentication():
    assert client.get("/jobs").status_code == 401
