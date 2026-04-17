"""Tests for authentication flow."""


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "models" in data


def test_login_success(client):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "wrongpass"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "noone", "password": "pass"},
    )
    assert resp.status_code == 401


def test_protected_endpoint_no_token(client):
    resp = client.get("/api/v1/jobs/fake-id")
    assert resp.status_code == 401


def test_protected_endpoint_with_token(client, auth_headers):
    resp = client.get("/api/v1/jobs/nonexistent-id", headers=auth_headers)
    # Should get 404 (job not found), not 401
    assert resp.status_code == 404
