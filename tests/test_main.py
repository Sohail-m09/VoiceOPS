from fastapi.testclient import TestClient

from voiceops.main import app

client = TestClient(app)


def test_app_metadata():
    assert app.title == "VoiceOps"
    assert app.version


def test_openapi_schema_is_served():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "VoiceOps"
