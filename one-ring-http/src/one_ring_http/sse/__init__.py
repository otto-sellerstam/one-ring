from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class ServerSentEvent:
    """Helper class for SSE encoding."""

    """The content for the event"""
    data: str

    """Event name"""
    event: str | None = None

    """ID of the event"""
    id: str | None = None

    """Number of milliseconds before reconnect"""
    retry: int | None = None

    """Comments. Ignored by client"""
    comment: str | None = None

    def encode(self) -> bytes:
        """Serializes to SSE protocol."""
        lines = []
        if self.comment is not None:
            lines.append(f": {self.comment}")
        if self.event is not None:
            lines.append(f"event: {self.event}")
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        lines.extend(f"data: {line}" for line in self.data.splitlines())
        lines.append("")
        return "\n".join(lines).encode() + b"\n"
