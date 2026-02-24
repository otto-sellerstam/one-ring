"""Tests for HTTP router."""

from typing import TYPE_CHECKING

from one_ring_http.request import Request
from one_ring_http.response import Response
from one_ring_http.router import Router, page_not_found

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPMethod


def _dummy_request(method: HTTPMethod = "GET", path: str = "/") -> Request:
    return Request(
        method=method, path=path, http_version="HTTP/1.1", headers={}, body=b""
    )


def _ok(_: Request) -> Response:
    return Response(status_code=200)


def _created(_: Request) -> Response:
    return Response(status_code=201)


def _teapot(_: Request) -> Response:
    return Response(status_code=418)


class TestRouter:
    def test_add_and_resolve(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        assert router.resolve("GET", "/hello") is _ok

    def test_resolve_unregistered_returns_fallback(self) -> None:
        router = Router()
        handler = router.resolve("GET", "/missing")
        result = handler(_dummy_request())
        assert isinstance(result, Response)
        assert result.status_code == 404

    def test_resolve_wrong_method_returns_fallback(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        resolved = router.resolve("POST", "/hello")
        assert resolved is not _ok

    def test_set_fallback(self) -> None:
        router = Router()
        router.set_fallback(_teapot)
        assert router.resolve("GET", "/anything") is _teapot

    def test_multiple_routes(self) -> None:
        router = Router()
        router.add("GET", "/a", _ok)
        router.add("POST", "/b", _created)
        assert router.resolve("GET", "/a") is _ok
        assert router.resolve("POST", "/b") is _created

    def test_overwrite_route(self) -> None:
        router = Router()
        router.add("GET", "/x", _ok)
        router.add("GET", "/x", _created)
        assert router.resolve("GET", "/x") is _created


class TestPageNotFound:
    def test_returns_404(self) -> None:
        result = page_not_found(_dummy_request())
        assert result.status_code == 404
