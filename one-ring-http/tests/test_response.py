"""Tests for HTTP response serialization."""

import json

from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus


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

    def test_serialize_exclude_body_omits_body(self) -> None:
        raw = Response(status_code=HTTPStatus.OK, body=b"hello").serialize(
            exclude_body=True
        )
        assert raw.endswith(b"\r\n\r\n")
        assert b"hello" not in raw

    def test_serialize_exclude_body_preserves_content_length(self) -> None:
        raw = Response(status_code=HTTPStatus.OK, body=b"hello").serialize(
            exclude_body=True
        )
        assert b"content-length: 5\r\n" in raw


class TestResponseHtml:
    def test_sets_html_content_type(self) -> None:
        r = Response.html("<h1>Hello</h1>")
        assert r.headers["content-type"] == "text/html; charset=utf-8"

    def test_encodes_body(self) -> None:
        r = Response.html("<p>Hi</p>")
        assert r.body == b"<p>Hi</p>"

    def test_default_status_ok(self) -> None:
        r = Response.html("")
        assert r.status_code == 200

    def test_custom_status_code(self) -> None:
        r = Response.html("<h1>Not Found</h1>", status_code=HTTPStatus.NOT_FOUND)
        assert r.status_code == 404


class TestResponseJson:
    def test_sets_json_content_type(self) -> None:
        r = Response.json({"key": "value"})
        assert r.headers["content-type"] == "application/json"

    def test_serializes_body_as_json(self) -> None:
        data = {"key": "value", "n": 42}
        r = Response.json(data)
        assert json.loads(r.body) == data

    def test_default_status_ok(self) -> None:
        r = Response.json({})
        assert r.status_code == 200

    def test_custom_status_code(self) -> None:
        r = Response.json({"id": 1}, status_code=HTTPStatus.CREATED)
        assert r.status_code == 201


class TestResponseText:
    def test_sets_text_content_type(self) -> None:
        r = Response.text("hello")
        assert r.headers["content-type"] == "text/plain; charset=utf-8"

    def test_encodes_body(self) -> None:
        r = Response.text("hello world")
        assert r.body == b"hello world"

    def test_default_status_ok(self) -> None:
        r = Response.text("")
        assert r.status_code == 200

    def test_custom_status_code(self) -> None:
        r = Response.text("bad", status_code=HTTPStatus.BAD_REQUEST)
        assert r.status_code == 400
