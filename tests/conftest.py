import pytest
from fastapi.testclient import TestClient

from backend.config import config
from backend.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("VIDEODOWNLOAD_LOCALHOST_BYPASS", "false")
    config.data.setdefault("server", {})["api_key"] = "test-secret-key"
    config.save()
    with TestClient(app) as c:
        yield c
