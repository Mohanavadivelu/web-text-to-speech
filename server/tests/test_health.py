from fastapi.testclient import TestClient

from server.api.main import app

client = TestClient(app)


def test_health_reports_ok():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
