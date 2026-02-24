from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.response import Response

if TYPE_CHECKING:
    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler, HTTPMethod


def page_not_found(_: Request) -> Response:
    """Default handler for 404."""
    return Response(status_code=404)


@dataclass(frozen=True, slots=True, kw_only=True)
class Router:
    """Routes HTTP request to handlers."""

    _registry: dict[tuple[HTTPMethod, str], HTTPHandler] = field(
        default_factory=dict, init=False
    )

    def add(self, method: HTTPMethod, path: str, handler: HTTPHandler) -> None:
        """Registers a path."""
        self._registry[(method, path)] = handler

    def resolve(self, method: HTTPMethod, path: str) -> HTTPHandler:
        """Returns the handler for a method and path."""
        handler = self._registry.get((method, path))
        if handler is None:
            return page_not_found
        return handler
