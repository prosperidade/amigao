from fastapi.testclient import TestClient

def test_create_process_unauthorized(client: TestClient):
    data = {"title": "Licenciamento de Teste", "client_id": 1}
    r = client.post("/api/v1/processes/", json=data)
    assert r.status_code == 401

def test_get_processes_unauthorized(client: TestClient):
    r = client.get("/api/v1/processes/")
    assert r.status_code == 401
