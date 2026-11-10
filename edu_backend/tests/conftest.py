"""pytest 配置：测试环境初始化。"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENABLE_FALLBACK_USERS", "true")

import pytest


@pytest.fixture
def settings():
    from config.settings import get_settings
    return get_settings()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import create_app
    app = create_app()
    return TestClient(app)
