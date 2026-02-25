"""Tests for HTTP response serialization."""

from one_ring_http.response import HTTPStatus, Response


class TestResponseSerialize:
    def test_minimal_response(self) -> None:
        raw = Response(status_code=HTTPStatus.OK).serialize()
        assert raw.startswith(b"HTTP/1.1 200 OK\r\ncontent-length: 0")

    def test_with_body(self) -> None:
        raw = Response(status_code=HTTPStatus.OK, body=b"hello").serialize()
        assert b"content-length: 5\r\n" in raw
        assert raw.endswith(b"\r\n\r\nhello")

    def test_with_custom_headers(self) -> None:
        raw = Response(
            status_code=HTTPStatus.NOT_FOUND,
            headers={"content-type": "text/html"},
            body=b"<h1>Not Found</h1>",
        ).serialize()
        assert raw.startswith(b"HTTP/1.1 404 Not found\r\n")
        assert b"content-type: text/html\r\n" in raw
        assert b"content-length: 18\r\n" in raw

    def test_multiple_custom_headers(self) -> None:
        raw = Response(
            status_code=HTTPStatus.OK,
            headers={"x-custom": "value1", "x-other": "value2"},
        ).serialize()
        assert b"x-custom: value1\r\n" in raw
        assert b"x-other: value2\r\n" in raw

    def test_empty_body_default(self) -> None:
        r = Response(status_code=HTTPStatus.NO_CONTENT)
        assert r.body == b""
        assert r.serialize().endswith(b"\r\n\r\n")
