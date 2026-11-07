"""认证与 RBAC 测试。"""
from app import db
from tests.conftest import auth, login


def test_passwords_are_bcrypt_hashed(client):
    rows = db.query("SELECT password_hash FROM sys_user")
    assert rows
    for row in rows:
        assert row["password_hash"].startswith("$2b$")
        assert "123456" not in row["password_hash"]


def test_login_success_and_me(client):
    token = login(client, "admin")
    response = client.get("/api/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_login_wrong_password(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_cookie_is_httponly(client):
    response = client.post(
        "/login", data={"username": "cashier", "password": "His@123456"}, follow_redirects=False
    )
    assert response.status_code == 303
    cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie


def test_anonymous_api_returns_401(client):
    assert client.get("/api/audit").status_code == 401
    assert client.get("/api/schedule/department?dept_name=内科&date=2026-11-07").status_code == 401


def test_cashier_cannot_access_admin_audit(client, cashier_token):
    response = client.get("/api/audit", headers=auth(cashier_token))
    assert response.status_code == 403


def test_admin_can_access_audit(client, admin_token):
    assert client.get("/api/audit", headers=auth(admin_token)).status_code == 200
    assert client.get("/audit", headers=auth(admin_token)).status_code == 200


def test_pharmacist_cannot_access_cashier(client, pharmacist_token):
    assert client.get("/cashier", headers=auth(pharmacist_token)).status_code == 403


def test_session_expiry_invalid_token(client):
    assert client.get("/api/auth/me", headers=auth("not-a-valid-token")).status_code == 401
