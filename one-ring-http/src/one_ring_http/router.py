import base64
import hashlib
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler, HTTPMethod, WebSocketHandler


def page_not_found(_: Request) -> Response:
    """Default handler for 404."""
    return Response(status_code=HTTPStatus.NOT_FOUND)


@dataclass(slots=True, kw_only=True)
class Router:
    """Routes HTTP request to handlers."""

    """Keeps tracks of registered HTTP handlers."""
    _registry: dict[tuple[HTTPMethod, str], HTTPHandler] = field(
        default_factory=dict, init=False
    )

    """Keeps tracks of registered HTTP 'handlers'"""
    _websocket_registry: dict[str, WebSocketHandler] = field(
        default_factory=dict, init=False
    )

    """Fallback for not found paths."""
    _fallback: HTTPHandler = field(default=page_not_found, init=False)

    def add(self, method: HTTPMethod, path: str, handler: HTTPHandler) -> None:
        """Registers a path."""
        self._registry[(method, path)] = handler

    def resolve(self, method: HTTPMethod, path: str) -> HTTPHandler:
        """Returns the handler for a method and path."""
        handler = self._registry.get((method, path))
        if handler is None and method == "HEAD":
            handler = self._registry.get(("GET", path))
        if handler is None:
            return self._fallback
        return handler

    def set_fallback(self, handler: HTTPHandler) -> None:
        """Sets fallback."""
        self._fallback = handler

    def register(
        self, method: HTTPMethod, path: str
    ) -> Callable[[HTTPHandler], HTTPHandler]:
        """Decorator to register HTTP endpoints."""

        def decorator(func: HTTPHandler) -> HTTPHandler:
            self.add(method, path, func)

            return func

        return decorator

    # Creating these dynamically messes with my type checker.
    def get(self, path: str) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for GET method registration."""
        return self.register("GET", path)

    def post(self, path: str) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for POST method registration."""
        return self.register("POST", path)

    def put(self, path: str) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for PUT method registration."""
        return self.register("PUT", path)

    def patch(self, path: str) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for PATCH method registration."""
        return self.register("PATCH", path)

    def delete(self, path: str) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for DELETE method registration."""
        return self.register("DELETE", path)

    def resolve_websocket(self, path: str) -> WebSocketHandler:
        """Fetches a websocket handler from a path."""
        return self._websocket_registry[path]

    def websocket(self, path: str) -> Callable[[WebSocketHandler], WebSocketHandler]:
        """For initializing a websocket connection."""

        def decorator(ws_handler: WebSocketHandler) -> WebSocketHandler:
            def ws_upgrade_http_handler(request: Request) -> Response:
                magic_string = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                with suppress(KeyError):
                    if (
                        request.headers["connection"].lower() == "upgrade"
                        and request.headers["upgrade"].lower() == "websocket"
                        and request.headers["sec-websocket-version"] == "13"
                    ):
                        key = request.headers["sec-websocket-key"]
                        accept = base64.b64encode(
                            hashlib.sha1(key.encode() + magic_string).digest()  # noqa: S324
                        ).decode()
                        return Response(
                            status_code=HTTPStatus.SWITCHING_PROTOCOLS,
                            headers={
                                "connection": "upgrade",
                                "upgrade": "websocket",
                                "sec-websocket-accept": accept,
                            },
                        )

                return Response(status_code=HTTPStatus.BAD_REQUEST)

            self.register("GET", path)(ws_upgrade_http_handler)

            self._websocket_registry[path] = ws_handler
            return ws_handler

        return decorator
