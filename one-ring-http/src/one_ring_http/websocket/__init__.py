from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Literal, Self, TypeIs

from one_ring_loop.cancellation import move_on_after

if TYPE_CHECKING:
    from one_ring_loop.streams.buffered import BufferedByteStream
    from one_ring_loop.typedefs import Coro


class WSConnectionClosedError(Exception):
    """Sentinel that WS connection has closed."""


class WSProtocolError(Exception):
    """Sentinal the WS frame did not follow protocol."""


class WSOpcode(IntEnum):
    """Opcodes for WS protocol."""

    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

    @classmethod
    def verify_opcode(cls, opcode: int) -> TypeIs[WSOpcode]:
        """Verifies that an opcode as int is part of the enum class."""
        return opcode in cls


type WSControlOpcode = Literal[WSOpcode.PING, WSOpcode.PONG, WSOpcode.CLOSE]


class WSCloseCode(IntEnum):
    """Common WS implementation side close codes."""

    NORMAL = 1000
    GOING_AWAY = 1001
    PROTOCOL_ERROR = 1002
    UNSUPPORTED_DATA = 1003
    NO_STATUS = 1005
    ABNORMAL = 1006
    INVALID_PAYLOAD = 1007
    POLICY_VIOLATION = 1008
    TOO_LARGE = 1009
    MISSING_EXTENSION = 1010
    INTERNAL_ERROR = 1011


FIN_BIT_MASK = 0x80
MASK_BIT_MASK = 0x80
OPCODE_MASK = 0x0F
PAYLOAD_LEN_MASK = 0x7F


LEN_2BYTE = 126
LEN_8BYTE = 127
MAX_LEN_1BYTE = 125
MAX_LEN_2BYTE = 2**16 - 1
MAX_LEN_8BYTE = 2**64 - 1


@dataclass(slots=True, kw_only=True)
class _WSFrame:
    """Data container for a parsed WS frame."""

    """If the frame is final. Used for fragmented frames"""
    final: bool

    """The opcode of the frame"""
    opcode: WSOpcode

    """Payload of the frame"""
    payload: bytes

    @classmethod
    def from_stream(cls, stream: BufferedByteStream) -> Coro[Self]:
        """Pulls data from stream to construct self."""
        raw_byte0 = yield from stream.receive_exactly(1)
        byte0 = int.from_bytes(raw_byte0)
        final = bool(int(byte0) >> 7)
        opcode = int(byte0) & OPCODE_MASK

        if not WSOpcode.verify_opcode(opcode):
            raise WSProtocolError("Received unsupported opcode")

        raw_byte1 = yield from stream.receive_exactly(1)
        byte1 = int.from_bytes(raw_byte1)
        mask = int(byte1) >> 7
        payload_length = int(byte1) & PAYLOAD_LEN_MASK

        if not mask:
            raise WSProtocolError("Client frame must be masked")

        if payload_length == LEN_2BYTE:
            raw_payload_length = yield from stream.receive_exactly(2)
            payload_length = int.from_bytes(raw_payload_length)
        elif payload_length == LEN_8BYTE:
            raw_payload_length = yield from stream.receive_exactly(8)
            payload_length = int.from_bytes(raw_payload_length)

        masking_key = yield from stream.receive_exactly(4)

        raw_payload = yield from stream.receive_exactly(payload_length)
        payload = bytes(
            raw_payload[i] ^ masking_key[i % 4] for i in range(payload_length)
        )

        if (
            opcode in (WSOpcode.PING, WSOpcode.PONG, WSOpcode.CLOSE)
            and payload_length > MAX_LEN_1BYTE
        ):
            raise WSProtocolError("Control frame payload exceeds 125 bytes")

        return cls(
            final=final,
            opcode=opcode,
            payload=payload,
        )


@dataclass(slots=True, kw_only=True)
class _WSCloseFrameData:
    """Parsed payload for a close frame."""

    """WS status code for the close frame"""
    status_code: int

    """Textual reasoning for the closure"""
    reason: str

    @classmethod
    def from_payload(cls, payload: bytes) -> Self:
        """Creates a WSCloseFrameData object by parsing a bytes payload."""
        if len(payload) < 2:  # noqa: PLR2004
            # No opcode or reason and provided.
            return cls(status_code=1005, reason="")
        status_code = int.from_bytes(payload[:2])
        reason = payload[2:].decode()
        return cls(
            status_code=status_code,
            reason=reason,
        )

    def encode(self) -> bytes:
        """Converts the WSCloseFrameData object to a payload."""
        return self.status_code.to_bytes(2) + self.reason.encode()


@dataclass(slots=True, kw_only=True)
class WebSocket:
    """Placeholder for future websocket object."""

    """Communication stream, used for HTTP before upgrade"""
    stream: BufferedByteStream

    _closing: bool = field(default=False, init=False, repr=False)

    def _handle_control_frame(
        self, opcode: WSControlOpcode, payload: bytes
    ) -> Coro[None]:
        match opcode:
            case WSOpcode.PING:
                yield from self._send(WSOpcode.PONG, payload)
            case WSOpcode.PONG:
                pass
            case WSOpcode.CLOSE:
                yield from self._send(WSOpcode.CLOSE, payload)
                close_data = _WSCloseFrameData.from_payload(payload)
                msg = (
                    f"Client closed connection with status {close_data.status_code}:"
                    f" {close_data.reason}"
                )
                raise WSConnectionClosedError(msg)

    def _is_control_frame(self, opcode: WSOpcode) -> TypeIs[WSControlOpcode]:
        return opcode in (WSOpcode.PING, WSOpcode.PONG, WSOpcode.CLOSE)

    def _receive_frame(self) -> Coro[_WSFrame]:
        """Receives and parses a singular frame.

        Raises:
            WSConnectionClosedError: on frame parsing error.
        """
        try:
            frame = yield from _WSFrame.from_stream(self.stream)
        except WSProtocolError as e:
            if not self._closing:
                yield from self.close(
                    WSCloseCode.PROTOCOL_ERROR,
                    reason="Sent frame does not follow WS protocol",
                )
            raise WSConnectionClosedError(
                "Error parsing frame. Frame does not follow WS protocol"
            ) from e
        return frame

    def receive(self) -> Coro[tuple[WSOpcode, bytes]]:
        """Receives and parses WS frame(s)."""
        while True:
            frame = yield from self._receive_frame()

            if self._is_control_frame(frame.opcode):
                yield from self._handle_control_frame(frame.opcode, frame.payload)
                continue

            # Extended on fragmented frames.
            payload_buffer = frame.payload

            while not frame.final:
                _frame = yield from self._receive_frame()

                if self._is_control_frame(_frame.opcode):
                    yield from self._handle_control_frame(_frame.opcode, _frame.payload)
                    continue

                if _frame.opcode != WSOpcode.CONTINUATION:
                    raise ValueError("Unexpected opcode during fragmentation handling")

                payload_buffer += _frame.payload
                frame.final = _frame.final  # Handling for potential control frames.

            if frame.opcode == WSOpcode.TEXT:
                try:
                    payload_buffer.decode()
                except UnicodeDecodeError as e:
                    yield from self.close(WSCloseCode.INVALID_PAYLOAD, "Invalid UTF-8")
                    raise WSConnectionClosedError(
                        "Received invalid UTF-8 in text frame"
                    ) from e

            return frame.opcode, payload_buffer

    def send_text(self, payload: str) -> Coro[None]:
        """Sends text data via websocket."""
        yield from self._send(WSOpcode.TEXT, payload.encode())

    def send_binary(self, payload: bytes) -> Coro[None]:
        """Sends binary data via websocket."""
        yield from self._send(WSOpcode.BINARY, payload)

    def close(self, status_code: int, reason: str) -> Coro[None]:
        """Sends a close frame to the client and waits for a response."""
        self._closing = True
        close_data = _WSCloseFrameData(status_code=status_code, reason=reason)
        yield from self._send(WSOpcode.CLOSE, close_data.encode())
        with move_on_after(5):
            while True:
                try:
                    yield from self.receive()
                except WSConnectionClosedError:
                    return

    def _send(self, opcode: WSOpcode, payload: bytes) -> Coro[None]:
        """Sends data via TCP connection using WS protocol."""
        data = bytearray()

        byte0 = FIN_BIT_MASK | opcode
        data.append(byte0)

        payload_length = len(payload)
        if payload_length <= MAX_LEN_1BYTE:
            data.append(payload_length)
        elif payload_length <= MAX_LEN_2BYTE:
            data.append(LEN_2BYTE)
            data.extend(payload_length.to_bytes(2))
        elif payload_length <= MAX_LEN_8BYTE:
            data.append(LEN_8BYTE)
            data.extend(payload_length.to_bytes(8))
        else:
            raise OverflowError("Payload is larger than 8 bytes")

        data.extend(payload)

        yield from self.stream.send(bytes(data))
