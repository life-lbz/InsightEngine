"""认证链路单元测试。"""
import pytest

from api.auth import create_access_token, create_refresh_token, verify_token


class TestJWT:
    def test_create_and_verify_access_token(self):
        token = create_access_token("user-001", ["course-1"], "student")
        payload = verify_token(token)
        assert payload["sub"] == "user-001"
        assert payload["role"] == "student"

    def test_create_and_verify_refresh_token(self):
        token = create_refresh_token("user-002")
        payload = verify_token(token)
        assert payload["sub"] == "user-002"

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            verify_token("invalid.token.here")


class TestFallbackUsers:
    def test_fallback_admin_login(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "admin"
        assert "access_token" in data

    def test_fallback_teacher_login(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "teacher", "password": "teacher123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "teacher"

    def test_fallback_student_login(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "student", "password": "student123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "student"

    def test_wrong_password_rejected(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
