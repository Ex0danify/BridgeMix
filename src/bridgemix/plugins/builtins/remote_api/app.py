"""
FastAPI application factory for the BridgeMix REST API.

Swagger UI is served at ``/docs`` and ReDoc at ``/redoc``; the raw OpenAPI schema
lives at ``/openapi.json``.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridgemix.plugins.device import (
    DeviceFacade,
    DeviceNotConnected,
    ParameterNotFound,
    ParameterOutOfRange,
    ParameterReadOnly,
)

API_TITLE = "BridgeMix REST API"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "Read and set Roland Bridge Cast parameters from third-party tools "
    "(Stream Deck, OBS, scripts).\n\n"
    "Parameter names are the same keys BridgeMix uses internally — call "
    "`GET /api/v1/parameters` to discover them along with their ranges.\n\n"
    "**Device connection:** every endpoint except `GET /api/v1/status` needs a "
    "connected device and returns `503` when none is — rather than serving stale "
    "cached values. Poll `/status` to know whether the device is connected.\n\n"
    "**Security:** the server binds to loopback and is *unauthenticated*. A guard "
    "rejects requests with an unexpected `Host` header (DNS-rebinding) or a "
    "cross-site `Origin` (a web page trying to reach your local API), so only "
    "local tools — curl, Stream Deck, this Swagger page — can reach it."
)

# Hostnames that always count as "this machine" for the Host-header guard.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _install_origin_guard(app: FastAPI, host: str, port: int) -> None:
    """Reject browser cross-site calls and unexpected Host headers.

    The API is loopback-only and unauthenticated, which leaves two browser-borne
    vectors: a malicious page POSTing to ``127.0.0.1`` (CSRF — CORS blocks reading
    the response, not the side effect) and DNS rebinding (a hostile domain
    re-resolved to loopback). We close both by only honouring requests whose Host
    is the address we bound, and rejecting any cross-origin ``Origin``. Same-origin
    requests (the Swagger "Try it out" button) and header-less tools (curl, Stream
    Deck) are unaffected.
    """
    wildcard = host in ("", "0.0.0.0", "::")
    allowed_hosts = None if wildcard else (_LOOPBACK_HOSTS | {host.lower()})
    origin_hosts = _LOOPBACK_HOSTS if wildcard else (_LOOPBACK_HOSTS | {host.lower()})
    allowed_origins = {f"http://{h}:{port}" for h in origin_hosts}

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        if allowed_hosts is not None:
            hostname = request.headers.get("host", "").rsplit(":", 1)[0].strip("[]").lower()
            if hostname and hostname not in allowed_hosts:
                return JSONResponse({"detail": "Host not allowed"}, status_code=403)
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
        return await call_next(request)


# ── Response / request models ──────────────────────────────────────────────────

class Status(BaseModel):
    connected: bool = Field(..., description="Whether a device is currently connected.")
    model: str | None = Field(None, description="Device model name, if known.")
    firmware: str | None = Field(None, description="Device firmware version, if known.")


class Parameter(BaseModel):
    name: str = Field(..., description="Stable parameter key.")
    value: int | None = Field(None, description="Current cached value (null if never synced).")
    min: int = Field(..., description="Minimum accepted value.")
    max: int = Field(..., description="Maximum accepted value.")
    default: int = Field(..., description="Device default value.")
    read_only: bool = Field(..., description="If true, the value cannot be written.")


class SetParameter(BaseModel):
    value: int = Field(..., description="New value; must lie within [min, max].")


def create_app(gateway: DeviceFacade, host: str = "127.0.0.1", port: int = 8765) -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION)
    _install_origin_guard(app, host, port)

    @app.exception_handler(DeviceNotConnected)
    async def _device_offline(request: Request, exc: DeviceNotConnected) -> JSONResponse:
        # Every device-data endpoint needs a live device; only /status answers
        # without one. So a disconnected device is a 503 across the board, rather
        # than serving stale cached values a client can't tell are stale.
        return JSONResponse({"detail": "No device connected"}, status_code=503)

    @app.get("/api/v1/status", response_model=Status, tags=["device"],
             summary="Device connection status")
    def get_status() -> dict:
        return gateway.status()

    @app.get("/api/v1/parameters", response_model=list[Parameter], tags=["parameters"],
             summary="List all parameters with ranges and current values")
    def list_parameters() -> list[dict]:
        return gateway.list_parameters()

    @app.get("/api/v1/parameters/{name}", response_model=Parameter, tags=["parameters"],
             summary="Get one parameter")
    def get_parameter(name: str) -> dict:
        try:
            return gateway.get_parameter(name)
        except ParameterNotFound:
            raise HTTPException(status_code=404, detail=f"Unknown parameter: {name}")

    @app.put("/api/v1/parameters/{name}", response_model=Parameter, tags=["parameters"],
             summary="Set one parameter")
    def set_parameter(name: str, body: SetParameter) -> dict:
        try:
            return gateway.set_parameter(name, body.value)
        except ParameterNotFound:
            raise HTTPException(status_code=404, detail=f"Unknown parameter: {name}")
        except ParameterReadOnly:
            raise HTTPException(status_code=409, detail=f"Parameter is read-only: {name}")
        except ParameterOutOfRange as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/api/v1/state", tags=["parameters"],
             summary="Flat name→value map of all cached values")
    def get_state() -> dict[str, int]:
        return gateway.state()

    return app
