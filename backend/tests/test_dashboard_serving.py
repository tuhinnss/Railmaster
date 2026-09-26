"""The deployed backend serves the built dashboard (RAILMASTER_FRONTEND_DIST,
see app/main.py and the Dockerfile); in development it doesn't."""

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main


@pytest.fixture
def main_with_dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>dashboard</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setenv("RAILMASTER_FRONTEND_DIST", str(tmp_path))
    yield importlib.reload(app.main)
    monkeypatch.delenv("RAILMASTER_FRONTEND_DIST")
    importlib.reload(app.main)  # back to the development app for other tests


def test_a_deployment_serves_the_dashboard_and_its_api_from_one_origin(main_with_dist):
    client = TestClient(main_with_dist.app)
    for route in ("/", "/control", "/overview"):
        assert client.get(route).text == "<html>dashboard</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/health").json() == {"status": "ok"}
    # Neither an unknown API path nor a missing build file comes back as the page.
    assert client.get("/api/nope").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404


def test_development_serves_only_the_api():
    client = TestClient(app.main.app)
    assert client.get("/control").status_code == 404
    assert client.get("/api/health").status_code == 200
