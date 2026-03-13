import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self

from one_ring_http.status import HTTPStatus
from one_ring_loop.streams.exceptions import EndOfStreamError

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPHeaders
    from one_ring_loop.streams.memory import MemoryObjectReceiveStream
    from one_ring_loop.typedefs import Coro


@dataclass(slots=True, kw_only=True)
class ResponseBase:
    """Base class for HTTP/1.1 responses to be serialized."""

    """HTTP status code of the response"""
    status_code: HTTPStatus

    """HTTP headers for the response"""
    headers: HTTPHeaders = field(default_factory=dict)

    @staticmethod
    def formatdate() -> str:
        """Formats current date and time for HTTP date format."""
        return datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

    def _serialize_head(self) -> bytes:
        status_line = (
            f"HTTP/1.1 {self.status_code} {self.status_code.phrase}\r\n".encode()
        )

        headers = f"date: {self.formatdate()}\r\n".encode()
        headers += b"server: one-ring-http/0.2.1\r\n"

        for header_name, header_val in self.headers.items():
            headers += f"{header_name}: {header_val}\r\n".encode()

        return status_line + headers


@dataclass(slots=True, kw_only=True)
class Response(ResponseBase):
    """A HTTP/1.1 response to be serialized."""

    """HTTP body for the response"""
    body: bytes = field(default=b"")

    def __post_init__(self) -> None:
        """Set default headers for basic response."""
        if self.status_code != HTTPStatus.SWITCHING_PROTOCOLS:
            self.headers["content-length"] = str(len(self.body))
        if self.body and "content-type" not in self.headers:
            self.headers["content-type"] = "text/plain; charset=utf-8"

    def serialize(self, exclude_body: bool = False) -> bytes:  # noqa: FBT001, FBT002
        """Serializes a response for transfer."""
        serialized_response = self._serialize_head()
        serialized_response += b"\r\n"

        if not exclude_body:
            serialized_response += self.body

        return serialized_response

    @classmethod
    def html(cls, body: str, status_code: HTTPStatus = HTTPStatus.OK) -> Self:
        """Utility function for HTML based response."""
        return cls(
            status_code=status_code,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body.encode(),
        )

    @classmethod
    def json(cls, data: dict, status_code: HTTPStatus = HTTPStatus.OK) -> Self:
        """Utility function for JSON based response."""
        return cls(
            status_code=status_code,
            headers={"content-type": "application/json"},
            body=json.dumps(data).encode(),
        )

    @classmethod
    def text(cls, body: str, status_code: HTTPStatus = HTTPStatus.OK) -> Self:
        """Utility function for text based response."""
        return cls(
            status_code=status_code,
            headers={"content-type": "text/plain; charset=utf-8"},
            body=body.encode(),
        )


@dataclass(slots=True, kw_only=True)
class StreamingResponse(ResponseBase):
    """For streamed responses (transfer-encoding: chunked)."""

    """Generator which streams the body as bytes"""
    body_stream: MemoryObjectReceiveStream[bytes]

    """Generator coroutine that produces value for the receive stream to fetch"""
    producer: Coro[None]

    _sent_head: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Specifies chunked response."""
        self.headers["transfer-encoding"] = "chunked"

    def serialize(self) -> Coro[bytes]:
        """Serializes the response and returns it in parts.

        Raises:
            EndOfStreamError: on subsequent calls after terminator chunk has been sent.
        """
        if self.body_stream.closed:
            raise EndOfStreamError
        if not self._sent_head:
            self._sent_head = True
            return self._serialize_head() + b"\r\n"

        try:
            chunk = yield from self.body_stream.receive()
        except EndOfStreamError:
            yield from self.body_stream.close()
            return self._serialize_chunk(b"")

        return self._serialize_chunk(chunk)

    @staticmethod
    def _serialize_chunk(chunk: bytes) -> bytes:
        return f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n"
