"""Tests for the REST-API routes (``bridgemix.plugins.builtins.remote_api.app``).

Uses FastAPI's TestClient against a *fake* gateway, so no Qt event loop or real
uvicorn server is involved — the marshalling itself is covered in
``test_device_facade``.  Skipped cleanly when the optional ``api`` dependencies
are not installed.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # required by starlette's TestClient

from fastapi.testclient import TestClient  # noqa: E402

from bridgemix.plugins.builtins.remote_api.app import create_app  # noqa: E402
from bridgemix.plugins.device import (  # noqa: E402
    DeviceNotConnected,
    ParameterNotFound,
    ParameterOutOfRange,
    ParameterReadOnly,
)


class FakeGateway:
    """Synchronous stand-in matching DeviceFacade's method surface."""

    def __init__(self, connected: bool = True) -> None:
        self._values = {"st_mic_vol": 100}
        self._meta = {"min": 0, "max": 127, "default": 100, "read_only": False}
        self.connected = connected

    def _describe(self, name: str) -> dict:
        return {"name": name, "value": self._values.get(name), **self._meta}

    def status(self) -> dict:
        if not self.connected:
            return {"connected": False, "model": None, "firmware": None}
        return {"connected": True, "model": "Roland Bridge Cast", "firmware": "3.00"}

    def list_parameters(self) -> list[dict]:
        if not self.connected:
            raise DeviceNotConnected()
        return [self._describe(n) for n in self._values]

    def get_parameter(self, name: str) -> dict:
        if name not in self._values:
            raise ParameterNotFound(name)
        if not self.connected:
            raise DeviceNotConnected(name)
        return self._describe(name)

    def set_parameter(self, name: str, value: int) -> dict:
        if name == "ro_param":
            raise ParameterReadOnly(name)
        if name not in self._values:
            raise ParameterNotFound(name)
        if not (self._meta["min"] <= value <= self._meta["max"]):
            raise ParameterOutOfRange(f"{value} out of range for {name}")
        if not self.connected:
            raise DeviceNotConnected(name)
        self._values[name] = value
        return self._describe(name)

    def state(self) -> dict:
        if not self.connected:
            raise DeviceNotConnected()
        return dict(self._values)


_HOST = "127.0.0.1"
_PORT = 8765


@pytest.fixture
def client():
    app = create_app(FakeGateway(), host=_HOST, port=_PORT)
    # base_url makes TestClient send a matching Host header (default is
    # "testserver", which the origin guard would reject).
    return TestClient(app, base_url=f"http://{_HOST}:{_PORT}")


def test_status(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json() == {
        "connected": True,
        "model": "Roland Bridge Cast",
        "firmware": "3.00",
    }


def test_list_parameters(client):
    r = client.get("/api/v1/parameters")
    assert r.status_code == 200
    assert r.json()[0]["name"] == "st_mic_vol"


def test_get_parameter(client):
    r = client.get("/api/v1/parameters/st_mic_vol")
    assert r.status_code == 200
    assert r.json()["value"] == 100


def test_get_unknown_parameter_404(client):
    r = client.get("/api/v1/parameters/nope")
    assert r.status_code == 404


def test_set_parameter_ok(client):
    r = client.put("/api/v1/parameters/st_mic_vol", json={"value": 42})
    assert r.status_code == 200
    assert r.json()["value"] == 42
    # And it is reflected in subsequent reads.
    assert client.get("/api/v1/state").json()["st_mic_vol"] == 42


def test_set_unknown_parameter_404(client):
    r = client.put("/api/v1/parameters/nope", json={"value": 1})
    assert r.status_code == 404


def test_set_readonly_409(client):
    r = client.put("/api/v1/parameters/ro_param", json={"value": 1})
    assert r.status_code == 409


def test_set_out_of_range_422(client):
    r = client.put("/api/v1/parameters/st_mic_vol", json={"value": 99999})
    assert r.status_code == 422


def test_set_missing_body_422(client):
    r = client.put("/api/v1/parameters/st_mic_vol", json={})
    assert r.status_code == 422


# ── Device disconnected ─────────────────────────────────────────────────────────

@pytest.fixture
def offline_client():
    app = create_app(FakeGateway(connected=False), host=_HOST, port=_PORT)
    return TestClient(app, base_url=f"http://{_HOST}:{_PORT}")


def test_set_while_disconnected_503():
    # Writing a perfectly valid parameter still fails — it can't reach the device.
    gateway = FakeGateway(connected=False)
    client = TestClient(create_app(gateway, host=_HOST, port=_PORT),
                        base_url=f"http://{_HOST}:{_PORT}")
    r = client.put("/api/v1/parameters/st_mic_vol", json={"value": 42})
    assert r.status_code == 503
    # And nothing was written.
    assert gateway._values["st_mic_vol"] == 100


def test_reads_blocked_while_disconnected(offline_client):
    # Device-data reads 503 too — no serving stale values a client can't vet.
    assert offline_client.get("/api/v1/parameters").status_code == 503
    assert offline_client.get("/api/v1/parameters/st_mic_vol").status_code == 503
    assert offline_client.get("/api/v1/state").status_code == 503


def test_status_always_answers_while_disconnected(offline_client):
    # /status is the one endpoint that works without a device.
    r = offline_client.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json()["connected"] is False


def test_validation_precedes_disconnect_check(offline_client):
    # A bad request is still a 4xx even when disconnected (no point reporting 503).
    assert offline_client.put("/api/v1/parameters/nope", json={"value": 1}).status_code == 404
    assert offline_client.put("/api/v1/parameters/ro_param", json={"value": 1}).status_code == 409
    assert offline_client.put(
        "/api/v1/parameters/st_mic_vol", json={"value": 99999}
    ).status_code == 422


def test_openapi_and_swagger_served(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


# ── Origin / Host guard ───────────────────────────────────────────────────────

def test_header_less_request_allowed(client):
    # curl / Stream Deck send no Origin and a loopback Host → allowed.
    assert client.get("/api/v1/status").status_code == 200


def test_same_origin_request_allowed(client):
    # The Swagger "Try it out" button sends the server's own origin.
    r = client.put(
        "/api/v1/parameters/st_mic_vol",
        json={"value": 7},
        headers={"Origin": f"http://{_HOST}:{_PORT}"},
    )
    assert r.status_code == 200


def test_cross_origin_request_blocked(client):
    # A malicious web page POSTing to the local API is rejected (CSRF defence).
    r = client.put(
        "/api/v1/parameters/st_mic_vol",
        json={"value": 7},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403


def test_unexpected_host_blocked(client):
    # DNS-rebinding: a hostile domain re-resolved to loopback is rejected.
    r = client.get("/api/v1/status", headers={"Host": "evil.example"})
    assert r.status_code == 403
