import functools
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.log import get_logger
from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from one_ring_http.request import Request
    from one_ring_http.typedef import AsyncHTTPHandler, HTTPMiddleware
    from one_ring_loop.typedefs import Coro

logger = get_logger()


@dataclass(frozen=True, slots=True, kw_only=True)
class MiddlewareStack:
    """Simple wrapper for registering and storing middleware."""

    _middleware: list[HTTPMiddleware] = field(default_factory=list, init=False)

    def register(self, func: HTTPMiddleware) -> HTTPMiddleware:
        """Registers a middleware function.

        First registered is innermost, last registered outermost.
        """
        self._middleware.append(func)

        return func

    def __iter__(self) -> Iterator[HTTPMiddleware]:
        """Returns iterator of middlewars in reversed order."""
        return reversed(self._middleware)


def exception_middleware(handler: AsyncHTTPHandler) -> AsyncHTTPHandler:
    """Logs incoming requests after parsing."""

    @functools.wraps(handler)
    def wrapper(request: Request) -> Coro[Response]:
        try:
            result = handler(request)
            response = yield from result
        except Exception:
            logger.exception()
            response = Response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                headers={"connection": "close", "content-type": "text/plain"},
            )

        return response

    return wrapper


def logging_middleware(handler: AsyncHTTPHandler) -> AsyncHTTPHandler:
    """Logs incoming requests after parsing."""

    @functools.wraps(handler)
    def wrapper(request: Request) -> Coro[Response]:
        logger.info("Incoming request", path=request.path, method=request.method)
        start_time = time.monotonic()
        result = handler(request)
        response = yield from result
        logger.info(
            "Sending response",
            path=request.path,
            method=request.method,
            status_code=response.status_code,
            elapsed_time=time.monotonic() - start_time,
        )
        return response

    return wrapper


def cors_middleware(allow_origin: str = "*") -> HTTPMiddleware:
    """Returns a middleware for CORS given an allowed origin.

    Should be registered with router last to be first middleware applied to request.
    """

    def middleware(handler: AsyncHTTPHandler) -> AsyncHTTPHandler:
        def wrapper(request: Request) -> Coro[Response]:
            if request.method == "OPTIONS":
                return Response(
                    status_code=HTTPStatus.NO_CONTENT,
                    headers={
                        "access-control-allow-origin": allow_origin,
                        "access-control-allow-methods": (
                            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                        ),
                        "access-control-allow-headers": "Content-Type, Authorization",
                        "access-control-max-age": "86400",
                    },
                )
            result = handler(request)
            response = yield from result
            response.headers["access-control-allow-origin"] = allow_origin
            return response

        return wrapper

    return middleware
