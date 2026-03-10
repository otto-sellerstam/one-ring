"""Tests for HTTP router."""

from typing import TYPE_CHECKING

from one_ring_http.response import Response
from one_ring_http.router import Router, page_not_found
from one_ring_http.status import HTTPStatus

from .conftest import make_request

if TYPE_CHECKING:
    from one_ring_http.request import Request


def _ok(_: Request) -> Response:
    return Response(status_code=HTTPStatus.OK)


def _created(_: Request) -> Response:
    return Response(status_code=HTTPStatus.CREATED)


def _teapot(_: Request) -> Response:
    return Response(status_code=HTTPStatus.TEAPOT)


class TestRouter:
    def test_add_and_resolve(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        handler, _ = router.resolve("GET", "/hello")
        assert handler is _ok

    def test_resolve_unregistered_returns_fallback(self) -> None:
        router = Router()
        handler, _ = router.resolve("GET", "/missing")
        result = handler(make_request())
        assert isinstance(result, Response)
        assert result.status_code == 404

    def test_resolve_wrong_method_returns_fallback(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        resolved = router.resolve("POST", "/hello")
        assert resolved is not _ok

    def test_set_fallback(self) -> None:
        router = Router()
        router.set_404_fallback(_teapot)
        handler, _ = router.resolve("GET", "/anything")
        assert handler is _teapot

    def test_overwrite_route(self) -> None:
        router = Router()
        router.add("GET", "/x", _ok)
        router.add("GET", "/x", _created)
        handler, _ = router.resolve("GET", "/x")
        assert handler is _created

    def test_head_falls_back_to_get(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        handler, _ = router.resolve("HEAD", "/hello")
        assert handler is _ok

    def test_explicit_head_takes_precedence(self) -> None:
        router = Router()
        router.add("GET", "/hello", _ok)
        router.add("HEAD", "/hello", _created)
        handler, _ = router.resolve("HEAD", "/hello")
        assert handler is _created


class TestPageNotFound:
    def test_returns_404(self) -> None:
        result = page_not_found(make_request())
        assert result.status_code == 404
