from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        yield client


def create_monitor(client):
    response = client.post("/monitors", json={"name": "Example", "url": "https://example.com"})
    assert response.status_code == 201
    return response.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_read_monitor(client):
    monitor = create_monitor(client)
    assert monitor["expected_status"] == 200
    assert client.get(f"/monitors/{monitor['id']}").json() == monitor
    assert client.get("/monitors").json() == [monitor]


@pytest.mark.parametrize("payload", [
    {"name": "", "url": "https://example.com"},
    {"name": "Example", "url": "invalid"},
    {"name": "Example", "url": "ftp://example.com"},
    {"name": "Example", "url": "https://example.com", "expected_status": 600},
])
def test_invalid_monitor(client, payload):
    assert client.post("/monitors", json=payload).status_code == 422


@pytest.mark.parametrize("path,method", [
    ("/monitors/999", "get"),
    ("/monitors/999/checks", "get"),
    ("/monitors/999/checks", "post"),
])
def test_missing_monitor(client, path, method):
    assert getattr(client, method)(path).status_code == 404


@pytest.mark.parametrize("status_code,is_up", [(200, True), (503, False)])
def test_check_and_history(client, monkeypatch, status_code, is_up):
    @contextmanager
    def fake_stream(method, url, **kwargs):
        assert method == "GET"
        assert kwargs["timeout"] == 5.0
        assert kwargs["follow_redirects"] is False
        yield httpx.Response(status_code)

    monkeypatch.setattr("app.main.httpx.stream", fake_stream)
    monitor = create_monitor(client)
    path = f"/monitors/{monitor['id']}/checks"
    response = client.post(path)
    assert response.status_code == 201
    check = response.json()
    assert check["is_up"] is is_up
    assert check["status_code"] == status_code
    assert check["error"] is None
    assert check["response_time_ms"] >= 0
    assert client.get(path).json() == [check]


def test_connection_failure_is_saved(client, monkeypatch):
    def failing_stream(*args, **kwargs):
        raise httpx.ConnectError("Connection failed")

    monkeypatch.setattr("app.main.httpx.stream", failing_stream)
    monitor = create_monitor(client)
    path = f"/monitors/{monitor['id']}/checks"
    check = client.post(path).json()
    assert check["is_up"] is False
    assert check["status_code"] is None
    assert check["error"] == "ConnectError"
    assert client.get(path).json() == [check]


def test_history_is_limited_and_isolated(client, monkeypatch):
    @contextmanager
    def fake_stream(*args, **kwargs):
        yield httpx.Response(200)

    monkeypatch.setattr("app.main.httpx.stream", fake_stream)
    first = create_monitor(client)
    second = create_monitor(client)
    path = f"/monitors/{first['id']}/checks"
    client.post(path)
    latest = client.post(path).json()
    assert client.get(path, params={"limit": 1}).json() == [latest]
    assert client.get(f"/monitors/{second['id']}/checks").json() == []
    assert client.get(path, params={"limit": 0}).status_code == 422


def test_data_survives_application_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "persistent.sqlite3"))
    with TestClient(app) as first_client:
        monitor = create_monitor(first_client)
    with TestClient(app) as second_client:
        assert second_client.get("/monitors").json() == [monitor]
