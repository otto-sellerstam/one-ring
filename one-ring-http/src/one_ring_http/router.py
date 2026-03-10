import base64
import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_http.request import Request
    from one_ring_http.typedef import (
        HTTPHandler,
        HTTPMethod,
        URLPath,
        URLPathParams,
        WebSocketHandler,
    )


def page_not_found(_: Request) -> Response:
    """Default handler for 404."""
    return Response(status_code=HTTPStatus.NOT_FOUND)


def http_method_not_allowed(_: Request) -> Response:
    """Default handler for HTTP method not allowed."""
    return Response(status_code=HTTPStatus.METHOD_NOT_ALLOWED)


@dataclass(slots=True, kw_only=True)
class Router:
    """Routes HTTP request to handlers."""

    """Keeps tracks of registered HTTP handlers."""
    _registry: dict[URLPath, dict[HTTPMethod, HTTPHandler]] = field(
        default_factory=dict, init=False
    )

    """Keeps tracks of registered HTTP 'handlers'"""
    _websocket_registry: dict[URLPath, WebSocketHandler] = field(
        default_factory=dict, init=False
    )

    """Fallback for not found paths."""
    fallback_404: HTTPHandler = field(default=page_not_found, init=False)

    """Fallback for not allowed methods."""
    fallback_405: HTTPHandler = field(default=http_method_not_allowed, init=False)

    def add(self, method: HTTPMethod, path: URLPath, handler: HTTPHandler) -> None:
        """Registers a path."""
        if path not in self._registry:
            self._registry[path] = {}
        self._registry[path][method] = handler

    def resolve(
        self, method: HTTPMethod, path: URLPath
    ) -> tuple[HTTPHandler, URLPathParams]:
        """Returns the handler for a method and path."""
        for registered_path in self._registry:
            pattern = self._compile_path(registered_path)
            if (path_params := pattern.match(path)) is not None:
                if (method_to_handler := self._registry.get(registered_path)) is None:
                    break
                handler = method_to_handler.get(method)

                if handler is None and method == "HEAD":
                    handler = method_to_handler.get("GET")
                if handler is None:
                    return self.fallback_405, {}
                return handler, path_params.groupdict()

        return self.fallback_404, {}

    def register(
        self, method: HTTPMethod, path: str
    ) -> Callable[[HTTPHandler], HTTPHandler]:
        """Decorator to register HTTP endpoints."""

        def decorator(func: HTTPHandler) -> HTTPHandler:
            self.add(method, path, func)

            return func

        return decorator

    def set_404_fallback(self, handler: HTTPHandler) -> None:
        """Sets the default 404 fallback."""
        self.fallback_404 = handler

    def set_405_fallback(self, handler: HTTPHandler) -> None:
        """Sets the default 405 fallback."""
        self.fallback_405 = handler

    # Creating these dynamically messes with my type checker.
    def get(self, path: URLPath) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for GET method registration."""
        return self.register("GET", path)

    def post(self, path: URLPath) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for POST method registration."""
        return self.register("POST", path)

    def put(self, path: URLPath) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for PUT method registration."""
        return self.register("PUT", path)

    def patch(self, path: URLPath) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for PATCH method registration."""
        return self.register("PATCH", path)

    def delete(self, path: URLPath) -> Callable[[HTTPHandler], HTTPHandler]:
        """Utility wrapper for DELETE method registration."""
        return self.register("DELETE", path)

    def resolve_websocket(self, path: URLPath) -> WebSocketHandler:
        """Fetches a websocket handler from a path."""
        return self._websocket_registry[path]

    def websocket(
        self, path: URLPath
    ) -> Callable[[WebSocketHandler], WebSocketHandler]:
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

    @staticmethod
    def _compile_path(pattern: URLPath) -> re.Pattern:
        """Replaces param_name with named capture group."""
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
        return re.compile(f"^{regex}$")
