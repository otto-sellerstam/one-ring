from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_http.typedef import HTTPHeaders


@dataclass(frozen=True, slots=True, kw_only=True)
class Response:
    """A HTTP/1.1 response to be serialized."""

    """HTTP status code of the response"""
    status_code: int

    """HTTP headers for the response"""
    headers: HTTPHeaders = field(default_factory=dict)

    """HTTP body for the response"""
    body: bytes = field(default=b"")

    def serialize(self) -> bytes:
        """Serializes a response for transfer."""
        # 1. Add first line
        serialized_response = f"HTTP/1.1 {self.status_code}\r\n".encode()

        # 2. Add headers
        content_length = len(self.body)
        serialized_response += f"content-length: {content_length}\r\n".encode()

        for header_name, header_val in self.headers.items():
            serialized_response += f"{header_name}: {header_val}\r\n".encode()

        serialized_response += b"\r\n"

        # 3. Add body
        serialized_response += self.body

        return serialized_response
