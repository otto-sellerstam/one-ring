from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, TypeGuard
from urllib import parse

from one_ring_loop.log import get_logger

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPHeaders, HTTPMethod, HTTPQueryParams
    from one_ring_loop.streams.buffered import BufferedByteReceiveStream
    from one_ring_loop.typedefs import Coro


logger = get_logger()

# Must match typedefs.HTTPMethod
ALLOWED_HTTP_METHODS: set[HTTPMethod] = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Request:
    """Represents a parsed HTTP/1.1 request."""

    """The HTTP method"""
    method: HTTPMethod

    """The URL path"""
    path: str

    """HTTP version"""
    http_version: str

    """HTTP headers"""
    headers: HTTPHeaders

    """HTTP body"""
    body: bytes

    """Query parameters"""
    query_params: HTTPQueryParams

    @classmethod
    def parse(cls, buffered_stream: BufferedByteReceiveStream) -> Coro[Self]:
        """Parses data from a buffered receive stream and provides a Request object."""
        # Get tokens from first line
        first_line = yield from buffered_stream.receive_until(
            delimiter=b"\r\n", max_bytes=65536
        )
        tokens = first_line.split(b" ")
        method = tokens[0].decode()
        target = tokens[1].decode()
        version = tokens[2].decode()

        if not cls.verify_http_method(method):
            raise RuntimeError("Unsupported HTTP method")

        # Get headers, until reaching empty line
        headers: HTTPHeaders = {}
        line = yield from buffered_stream.receive_until(
            delimiter=b"\r\n", max_bytes=65536
        )
        while line:
            key_val = line.split(b": ", 1)
            header_name = key_val[0].decode().lower()
            header_val = key_val[1].decode()

            if header_name in headers:
                header_val = headers[header_name] + ", " + header_val

            headers[header_name] = header_val
            line = yield from buffered_stream.receive_until(
                delimiter=b"\r\n", max_bytes=65536
            )

        # Get body, if we have "content-length"
        body = b""
        if "content-length" in headers:
            content_length = int(headers["content-length"])
            body = yield from buffered_stream.receive_exactly(content_length)

        # Get query params from target path.
        parsed = parse.urlparse(target)

        return cls(
            method=method,
            path=parsed.path,
            http_version=version,
            headers=headers,
            body=body,
            query_params=parse.parse_qs(parsed.query),
        )

    @staticmethod
    def verify_http_method(method: str) -> TypeGuard[HTTPMethod]:
        """Verifies that HTTP method is valid."""
        return method in ALLOWED_HTTP_METHODS
