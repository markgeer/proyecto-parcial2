import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pytest_html import extras as html_extras
import requests

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@test.com")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

REPORTS = Path("reports")
RESULTS = REPORTS / "results.jsonl"   # una línea JSON por prueba (luego se envía a OpenObserve)


def pytest_configure(config):
    REPORTS.mkdir(exist_ok=True)
    RESULTS.write_text("")


def pytest_html_report_title(report):
    report.title = "Reporte de pruebas - Proyecto Parcial 2"


class Api:
    """Cliente HTTP que registra cada petición (método, ruta, status code, timestamp)."""

    def __init__(self, base_url):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.token = None
        self.calls = []

    def request(self, method, path, auth=True, token=None, **kw):
        headers = kw.pop("headers", {})
        t = token if token is not None else (self.token if auth else None)
        if t:
            headers["Authorization"] = f"Bearer {t}"
        r = self.session.request(method, self.base + path, headers=headers, timeout=10, **kw)
        self.calls.append({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": method,
            "path": path,
            "status": r.status_code,
            "ms": round(r.elapsed.total_seconds() * 1000),
        })
        return r

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)


@pytest.fixture(scope="session")
def admin_token(base_url):
    r = requests.post(base_url + "/api/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=10)
    assert r.status_code == 200, f"No se pudo hacer login como admin: {r.text}"
    return r.json()["token"]


@pytest.fixture
def api(base_url, admin_token):
    a = Api(base_url)
    a.token = admin_token
    return a


@pytest.fixture
def make_user(api):
    def _make(**over):
        data = {"name": "Usuario Test", "email": f"u_{uuid.uuid4().hex[:8]}@test.com",
                "password": "Pass1234", "role": "user"}
        data.update(over)
        r = api.post("/api/users", json=data)
        assert r.status_code == 201, r.text
        return {**data, **r.json()}
    return _make


@pytest.fixture
def make_product(api):
    def _make(**over):
        data = {"name": f"Producto {uuid.uuid4().hex[:6]}", "price": 12.5, "stock": 3}
        data.update(over)
        r = api.post("/api/products", json=data)
        assert r.status_code == 201, r.text
        return {**data, **r.json()}
    return _make


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return

    extras = getattr(report, "extras", [])
    page = item.funcargs.get("page")
    api = item.funcargs.get("api")
    calls = api.calls if api else []

    # Captura de pantalla (pruebas de frontend), pasen o fallen
    if page is not None:
        try:
            png = page.screenshot(full_page=True)
            extras.append(html_extras.png(base64.b64encode(png).decode()))
        except Exception:
            pass

    # Tabla de peticiones HTTP (pruebas de API)
    if calls:
        rows = "".join(
            f"<tr><td>{c['timestamp']}</td><td>{c['method']}</td><td>{c['path']}</td>"
            f"<td>{c['status']}</td><td>{c['ms']} ms</td></tr>" for c in calls)
        extras.append(html_extras.html(
            "<table border='1' cellpadding='4' style='border-collapse:collapse'>"
            "<tr><th>Timestamp (UTC)</th><th>Método</th><th>Endpoint</th><th>Status</th><th>Tiempo</th></tr>"
            f"{rows}</table>"))

    report.extras = extras

    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "test": item.name,
            "type": "frontend" if page is not None else "backend",
            "outcome": report.outcome,
            "duration_s": round(report.duration, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status_codes": [c["status"] for c in calls],
            "endpoints": [f"{c['method']} {c['path']}" for c in calls],
        }, ensure_ascii=False) + "\n")