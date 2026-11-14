from fastapi.testclient import TestClient

from voiceops import __version__
from voiceops.config import get_settings
from voiceops.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "version": __version__,
        "environment": get_settings().app_env,
    }


def test_health_only_accepts_get():
    assert client.post("/health").status_code == 405
