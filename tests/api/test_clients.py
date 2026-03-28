from fastapi.testclient import TestClient

def test_create_client_unauthorized(client: TestClient):
    data = {
        "name": "Test Client",
        "email": "client@example.com",
        "document": "12345678901",
        "client_type": "pf"
    }
    # No auth token provided, should get 401
    r = client.post("/api/v1/clients/", json=data)
    assert r.status_code == 401

def test_get_clients_unauthorized(client: TestClient):
    r = client.get("/api/v1/clients/")
    assert r.status_code == 401
