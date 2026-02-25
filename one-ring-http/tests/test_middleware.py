"""Tests for HTTP middleware."""

from collections.abc import Generator
from typing import TYPE_CHECKING

from one_ring_http.middleware import cors_middleware
from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus
from one_ring_loop.timerio import sleep

from .conftest import make_request

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler
    from one_ring_loop.typedefs import Coro


def _invoke_handler(handler: HTTPHandler, request: Request) -> Coro[Response]:
    """Drive a handler that may return a Response or a generator."""
    result = handler(request)
    if isinstance(result, Generator):
        response = yield from result
    else:
        response = result
    return response


class TestCorsMiddleware:
    def test_options_returns_204_with_preflight_headers(
        self, run_coro: Callable[[Coro], object]
    ) -> None:
        wrapped = cors_middleware()(lambda req: Response(status_code=HTTPStatus.OK))
        request = make_request(method="OPTIONS")

        def entry() -> Coro[None]:
            response = yield from _invoke_handler(wrapped, request)
            assert response.status_code == 204
            assert response.headers["access-control-allow-origin"] == "*"
            assert (
                response.headers["access-control-allow-methods"]
                == "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            assert (
                response.headers["access-control-allow-headers"]
                == "Content-Type, Authorization"
            )
            assert response.headers["access-control-max-age"] == "86400"

        run_coro(entry())

    def test_adds_origin_header_to_get_response(
        self, run_coro: Callable[[Coro], object]
    ) -> None:
        wrapped = cors_middleware()(
            lambda req: Response(status_code=HTTPStatus.OK, body=b"hello")
        )
        request = make_request(method="GET")

        def entry() -> Coro[None]:
            response = yield from _invoke_handler(wrapped, request)
            assert response.status_code == 200
            assert response.body == b"hello"
            assert response.headers["access-control-allow-origin"] == "*"

        run_coro(entry())

    def test_custom_allow_origin(self, run_coro: Callable[[Coro], object]) -> None:
        origin = "https://example.com"
        wrapped = cors_middleware(origin)(
            lambda req: Response(status_code=HTTPStatus.OK)
        )

        def entry() -> Coro[None]:
            options_resp = yield from _invoke_handler(
                wrapped, make_request(method="OPTIONS")
            )
            assert options_resp.headers["access-control-allow-origin"] == origin

            get_resp = yield from _invoke_handler(wrapped, make_request(method="GET"))
            assert get_resp.headers["access-control-allow-origin"] == origin

        run_coro(entry())

    def test_works_with_async_handler(self, run_coro: Callable[[Coro], object]) -> None:
        def async_handler(req: Request) -> Coro[Response]:
            yield from sleep(0)
            return Response(status_code=HTTPStatus.OK, body=b"async")

        wrapped = cors_middleware()(async_handler)
        request = make_request(method="GET")

        def entry() -> Coro[None]:
            response = yield from _invoke_handler(wrapped, request)
            assert response.status_code == 200
            assert response.body == b"async"
            assert response.headers["access-control-allow-origin"] == "*"

        run_coro(entry())
