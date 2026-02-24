"""Shared test fixtures for one-ring-http."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPHeaders
    from one_ring_loop.streams.buffered import BufferedByteReceiveStream
    from one_ring_loop.typedefs import Coro


@dataclass(frozen=True, slots=True, kw_only=True)
class RawHTTPResponse:
    """Parsed raw HTTP response from a buffered stream."""

    status_code: int
    headers: HTTPHeaders
    body: bytes


def parse_raw_response(stream: BufferedByteReceiveStream) -> Coro[RawHTTPResponse]:
    """Reads and parses a raw HTTP response from a buffered byte stream."""
    status_line = yield from stream.receive_until(delimiter=b"\r\n", max_bytes=65536)
    status_code = int(status_line.split(b" ", 2)[1])

    headers: dict[str, str] = {}
    line = yield from stream.receive_until(delimiter=b"\r\n", max_bytes=65536)
    while line:
        key, val = line.split(b": ", 1)
        headers[key.decode().lower()] = val.decode()
        line = yield from stream.receive_until(delimiter=b"\r\n", max_bytes=65536)

    body = b""
    if "content-length" in headers:
        body = yield from stream.receive_exactly(int(headers["content-length"]))

    return RawHTTPResponse(status_code=status_code, headers=headers, body=body)
