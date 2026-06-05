"""Remote API plugin: wraps the HTTP server and its control widget.

create_widget builds the server on the context's DeviceFacade, restores the saved
enabled state from the SDK settings store and returns the card; shutdown stops the
server.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from bridgemix.plugins import Plugin, PluginContext
from bridgemix.plugins.builtins.remote_api.server import ApiServer
from bridgemix.plugins.builtins.remote_api.settings import from_store
from bridgemix.plugins.builtins.remote_api.widget import RemoteApiWidget


class RemoteApiPlugin(Plugin):
    def __init__(self) -> None:
        self._server: ApiServer | None = None

    def create_widget(self, ctx: PluginContext) -> QWidget:
        self._server = ApiServer(ctx.device)
        widget = RemoteApiWidget(ctx, self._server)

        # Auto-start if it was left enabled.
        settings = from_store(ctx.settings)
        if settings.enabled:
            self._server.start(settings)

        return widget

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None
