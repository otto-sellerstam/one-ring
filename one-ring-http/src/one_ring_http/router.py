from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.response import HTTPStatus, Response

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler, HTTPMethod


def page_not_found(_: Request) -> Response:
    """Default handler for 404."""
    return Response(status_code=HTTPStatus.NOT_FOUND)


@dataclass(slots=True, kw_only=True)
class Router:
    """Routes HTTP request to handlers."""

    _registry: dict[tuple[HTTPMethod, str], HTTPHandler] = field(
        default_factory=dict, init=False
    )

    _fallback: HTTPHandler = field(default=page_not_found, init=False)

    def add(self, method: HTTPMethod, path: str, handler: HTTPHandler) -> None:
        """Registers a path."""
        self._registry[(method, path)] = handler

    def resolve(self, method: HTTPMethod, path: str) -> HTTPHandler:
        """Returns the handler for a method and path."""
        handler = self._registry.get((method, path))
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

        def wrapper(func: HTTPHandler) -> HTTPHandler:
            self.add(method, path, func)

            return func

        return wrapper

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
