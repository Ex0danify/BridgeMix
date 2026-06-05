"""End-to-end integration test for the REST API."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from bridgemix.plugins.builtins.remote_api.server import ApiServer  # noqa: E402
from bridgemix.plugins.device import DeviceFacade  # noqa: E402
from bridgemix.plugins.builtins.remote_api.settings import ApiSettings  # noqa: E402
from bridgemix.device.parameters import REGISTRY  # noqa: E402


class StubBridge(QObject):
    connected = pyqtSignal(bool)
    parameter_changed = pyqtSignal(str, int)
    device_info_updated = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._state = {name: p.default_value for name, p in REGISTRY.items()}
        self._is_connected = True

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def state(self) -> dict[str, int]:
        return dict(self._state)

    def set_parameter(self, name: str, value: int) -> None:
        self._state[name] = value


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _request_in_worker(qapp, fn, timeout=10.0):
    """Run blocking *fn* on a worker thread while pumping the Qt loop here."""
    box: dict = {}

    def worker():
        try:
            box["result"] = fn()
        except BaseException as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=worker)
    t.start()
    deadline = time.monotonic() + timeout
    while t.is_alive() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    t.join(timeout=2.0)
    if "error" in box:
        raise box["error"]
    return box["result"]


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, json.loads(r.read())


def _put_json(url: str, body: dict):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


@pytest.fixture
def live_server(qapp):
    bridge = StubBridge()
    gateway = DeviceFacade(bridge)
    bridge.device_info_updated.emit("Roland Bridge Cast", "3.00")  # after facade connects
    server = ApiServer(gateway)
    settings = ApiSettings(enabled=True, host="127.0.0.1", port=_free_port())
    assert server.start(settings) is True
    try:
        yield server, settings, bridge
    finally:
        server.stop()
        assert server.is_running is False


def test_status_over_real_http(qapp, live_server):
    server, settings, _ = live_server
    base = f"http://127.0.0.1:{settings.port}"
    status, body = _request_in_worker(qapp, lambda: _get_json(f"{base}/api/v1/status"))
    assert status == 200
    assert body["connected"] is True
    assert body["model"] == "Roland Bridge Cast"


def test_set_round_trips_through_gateway_and_device(qapp, live_server):
    server, settings, bridge = live_server
    base = f"http://127.0.0.1:{settings.port}"
    name = next(n for n, p in REGISTRY.items() if not p.read_only and p.min_value < p.max_value)
    target = REGISTRY[name].min_value

    status, body = _request_in_worker(
        qapp, lambda: _put_json(f"{base}/api/v1/parameters/{name}", {"value": target})
    )
    assert status == 200
    assert body["value"] == target
    # The write reached the (stub) device via the marshalling gateway...
    assert bridge.state[name] == target
    # ...and is visible on a subsequent read.
    _, state = _request_in_worker(qapp, lambda: _get_json(f"{base}/api/v1/state"))
    assert state[name] == target
