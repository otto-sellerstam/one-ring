from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPHeaders


@dataclass(frozen=True, slots=True, kw_only=True)
class Response:
    """A HTTP/1.1 response to be serialized."""

    """HTTP status code of the response"""
    status_code: HTTPStatus

    """HTTP headers for the response"""
    headers: HTTPHeaders = field(default_factory=dict)

    """HTTP body for the response"""
    body: bytes = field(default=b"")

    def serialize(self, exclude_body: bool = False) -> bytes:  # noqa: FBT001, FBT002
        """Serializes a response for transfer."""
        # 1. Add first line
        serialized_response = (
            f"HTTP/1.1 {self.status_code} {self.status_code.phrase}\r\n".encode()
        )

        # 2. Add headers
        content_length = len(self.body)
        serialized_response += f"content-length: {content_length}\r\n".encode()

        if self.body and "content-type" not in self.headers:
            serialized_response += b"content-type: text/plain; charset=utf-8\r\n"

        serialized_response += f"date: {self.formatdate()}\r\n".encode()
        serialized_response += b"server: one-ring-http/0.1.0\r\n"

        for header_name, header_val in self.headers.items():
            serialized_response += f"{header_name}: {header_val}\r\n".encode()

        # 3. Add delimiter
        serialized_response += b"\r\n"

        # 4. Add body
        if not exclude_body:
            serialized_response += self.body

        return serialized_response

    @staticmethod
    def formatdate() -> str:
        """Formats current date and time for HTTP date format."""
        return datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


class HTTPStatus(IntEnum):
    """HTTP status codes with reason phrases."""

    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    FORBIDDEN = 403
    NOT_FOUND = 404
    TEAPOT = 418
    INTERNAL_SERVER_ERROR = 500

    @property
    def phrase(self) -> str:
        """Gets the corresponding reason phrase."""
        return _PHRASES[self]


_PHRASES: dict[HTTPStatus, str] = {
    HTTPStatus.OK: "OK",
    HTTPStatus.CREATED: "Created succesfully",
    HTTPStatus.NO_CONTENT: "No content",
    HTTPStatus.NOT_MODIFIED: "Not modified",
    HTTPStatus.BAD_REQUEST: "Bad request",
    HTTPStatus.FORBIDDEN: "Forbidden",
    HTTPStatus.NOT_FOUND: "Not found",
    HTTPStatus.TEAPOT: "I'm a teapot",
    HTTPStatus.INTERNAL_SERVER_ERROR: "Internal server error",
}
