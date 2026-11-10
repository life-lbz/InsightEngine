"""健康检查与系统端点测试。"""
import pytest


class TestHealth:
    def test_debug_ping(self, client):
        resp = client.get("/api/v1/debug/ping")
        assert resp.status_code == 200
        assert resp.json()["pong"] is True

    def test_root_health(self, client):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
