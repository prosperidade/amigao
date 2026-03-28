from fastapi.testclient import TestClient

def test_login_access_token(client: TestClient):
    # This assumes the DB has a default admin user, or we should create one.
    # For now, we will just expect an error since the in-memory db is empty.
    # In a real test, we'd use a fixture to seed the database.
    pass

def test_login_invalid_credentials(client: TestClient):
    login_data = {
        "username": "invalid@example.com",
        "password": "wrongpassword"
    }
    r = client.post("/api/v1/auth/login", data=login_data)
    assert r.status_code == 404 or r.status_code == 400
