"""Tests for HTTP request parsing and validation."""

from typing import TYPE_CHECKING

import pytest

from one_ring_http.request import Request
from one_ring_loop.streams.buffered import BufferedByteReceiveStream
from one_ring_loop.streams.memory import create_memory_object_stream

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_loop.typedefs import Coro


class TestVerifyHTTPMethod:
    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    def test_valid_methods(self, method: str) -> None:
        assert Request.verify_http_method(method) is True

    @pytest.mark.parametrize(
        "method", ["get", "OPTIONS", "HEAD", "CONNECT", "", "INVALID"]
    )
    def test_invalid_methods(self, method: str) -> None:
        assert Request.verify_http_method(method) is False


class TestRequestParse:
    def test_simple_get(self, run_coro: Callable[[Coro], object]) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(b"GET /hello HTTP/1.1\r\nhost: localhost\r\n\r\n")
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.method == "GET"
            assert request.path == "/hello"
            assert request.http_version == "HTTP/1.1"
            assert request.headers == {"host": "localhost"}
            assert request.body == b""

        run_coro(entry())

    def test_post_with_body(self, run_coro: Callable[[Coro], object]) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(
                b"POST /submit HTTP/1.1\r\n"
                b"host: localhost\r\n"
                b"content-length: 13\r\n"
                b"\r\n"
                b"hello, world!"
            )
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.method == "POST"
            assert request.path == "/submit"
            assert request.body == b"hello, world!"

        run_coro(entry())

    def test_multiple_headers(self, run_coro: Callable[[Coro], object]) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(
                b"GET / HTTP/1.1\r\n"
                b"host: example.com\r\n"
                b"accept: text/html\r\n"
                b"user-agent: test\r\n"
                b"\r\n"
            )
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.headers["host"] == "example.com"
            assert request.headers["accept"] == "text/html"
            assert request.headers["user-agent"] == "test"

        run_coro(entry())

    def test_header_names_lowercased(self, run_coro: Callable[[Coro], object]) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(b"GET / HTTP/1.1\r\nHost: EXAMPLE.COM\r\n\r\n")
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert "host" in request.headers
            assert "Host" not in request.headers

        run_coro(entry())

    def test_duplicate_headers_concatenated(
        self, run_coro: Callable[[Coro], object]
    ) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(
                b"GET / HTTP/1.1\r\n"
                b"accept: text/html\r\n"
                b"accept: application/json\r\n"
                b"\r\n"
            )
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.headers["accept"] == "text/html, application/json"

        run_coro(entry())

    def test_all_duplicate_headers_concatenated(
        self, run_coro: Callable[[Coro], object]
    ) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(
                b"GET / HTTP/1.1\r\nset-cookie: a=1\r\nset-cookie: b=2\r\n\r\n"
            )
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.headers["set-cookie"] == "a=1, b=2"

        run_coro(entry())

    def test_chunked_delivery(self, run_coro: Callable[[Coro], object]) -> None:
        raw = b"GET /path HTTP/1.1\r\nhost: localhost\r\n\r\n"

        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            for i in range(0, len(raw), 5):
                yield from send.send(raw[i : i + 5])
            yield from send.close()

            request = yield from Request.parse(buffered)
            assert request.method == "GET"
            assert request.path == "/path"

        run_coro(entry())

    def test_invalid_method_raises(self, run_coro: Callable[[Coro], object]) -> None:
        def entry() -> Coro[None]:
            send, recv = create_memory_object_stream[bytes](None)
            buffered = BufferedByteReceiveStream(receive_stream=recv)
            yield from send.send(b"INVALID /path HTTP/1.1\r\nhost: localhost\r\n\r\n")
            yield from send.close()
            yield from Request.parse(buffered)

        with pytest.raises(RuntimeError):
            run_coro(entry())
