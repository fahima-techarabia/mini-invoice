"""The app, its routes and its templates load without a database connection."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import checks, db, services
from app.main import app
from app.web import templates

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

ROUTES = [
    ("GET", "/"),
    ("GET", "/invoices"),
    ("GET", "/queries"),
    ("GET", "/invoices/new"),
    ("POST", "/invoices/new"),
    ("GET", "/invoices/INV-0000"),
    ("GET", "/invoices/INV-0000/edit"),
    ("POST", "/invoices/INV-0000/edit"),
    ("POST", "/invoices/INV-0000/delete"),
    ("GET", "/api/invoices"),
    ("POST", "/api/invoices"),
    ("GET", "/api/invoices/INV-0000"),
    ("PUT", "/api/invoices/INV-0000"),
    ("DELETE", "/api/invoices/INV-0000"),
]


def _no_database():
    raise RuntimeError("This test must not open a database.")


@pytest.fixture()
def offline_client(monkeypatch):
    for module in (services, checks, db):
        monkeypatch.setattr(module, "get_db", _no_database)
    monkeypatch.setattr(db, "get_client", _no_database)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("method, path", ROUTES)
def test_route_is_registered(offline_client, method, path):
    response = offline_client.request(method, path, follow_redirects=False)
    assert response.status_code not in (404, 405), response.text[:200]


def test_unknown_page_is_not_found(offline_client):
    assert offline_client.get("/no-such-page").status_code == 404


@pytest.mark.parametrize("name", sorted(path.name for path in TEMPLATES.glob("*.html")))
def test_template_compiles(name):
    templates.env.get_template(name)
