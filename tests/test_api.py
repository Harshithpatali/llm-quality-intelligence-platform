from fastapi.testclient import TestClient
from backend.main import app
client=TestClient(app)

def test_health():
    assert client.get("/health").json()["status"]=="ok"

def test_benchmark_endpoint():
    response=client.get("/benchmark")
    assert response.status_code==200
    assert response.json()["count"]>=100
