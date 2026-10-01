from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_benchmark_is_public_and_has_cases():
    response = client.get("/benchmark")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 60
    assert len(payload["cases"]) == payload["count"]


def test_run_request_validation():
    response = client.post(
        "/benchmark/run",
        json={"providers": ["unsupported-provider"], "limit": 5},
    )
    assert response.status_code == 422
