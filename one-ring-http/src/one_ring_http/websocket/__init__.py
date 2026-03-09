from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_loop.streams.buffered import BufferedByteStream
    from one_ring_loop.typedefs import Coro


class ConnectionClosedError(Exception):
    """Sentinel that WS connection has closed."""


class WSOpcode(IntEnum):
    """Opcodes for WS protocol."""

    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


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
class WebSocket:
    """Placeholder for future websocket object."""

    """Communication stream, used for HTTP before upgrade"""
    stream: BufferedByteStream

    def _read_frame(self) -> Coro[tuple[int, bytes]]:
        """Reads a frame and returns opcode and payload."""
        raw = yield from self.stream.receive_exactly(1)
        byte0 = int.from_bytes(raw)
        # final = int(byte0) >> 7
        opcode = int(byte0) & OPCODE_MASK

        raw = yield from self.stream.receive_exactly(1)
        byte1 = int.from_bytes(raw)
        mask = int(byte1) >> 7
        payload_length = int(byte1) & PAYLOAD_LEN_MASK

        if payload_length == LEN_2BYTE:
            raw = yield from self.stream.receive_exactly(2)
            payload_length = int.from_bytes(raw)
        elif payload_length == LEN_8BYTE:
            raw = yield from self.stream.receive_exactly(8)
            payload_length = int.from_bytes(raw)

        masking_key = None
        if mask:
            masking_key = yield from self.stream.receive_exactly(4)

        payload = yield from self.stream.receive_exactly(payload_length)
        if masking_key is not None:
            payload = bytes(
                payload[i] ^ masking_key[i % 4] for i in range(payload_length)
            )

        return opcode, payload

    def receive(self) -> Coro[tuple[WSOpcode, bytes]]:
        """Receives data via the TCP connection and parses it using WS protocol."""
        while True:
            opcode, payload = yield from self._read_frame()

            match opcode:
                case WSOpcode.PING:
                    yield from self.send(WSOpcode.PONG, payload)
                case WSOpcode.PONG:
                    pass
                case WSOpcode.CLOSE:
                    yield from self.send(WSOpcode.CLOSE, payload)
                    raise ConnectionClosedError("Client closed the connection")
                case WSOpcode.CONTINUATION | WSOpcode.TEXT | WSOpcode.BINARY:
                    return opcode, payload
                case _:
                    raise ValueError("Unsupported opcode")

    def send_test(self, payload: str) -> Coro[None]:
        """Sends text data via websocket."""
        yield from self.send(WSOpcode.TEXT, payload.encode())

    def send_binary(self, payload: bytes) -> Coro[None]:
        """Sends text data via websocket."""
        yield from self.send(WSOpcode.BINARY, payload)

    def send(self, opcode: WSOpcode, payload: bytes) -> Coro[None]:
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
