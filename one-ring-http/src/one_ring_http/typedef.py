from collections.abc import Callable
from typing import Literal

from one_ring_http.request import Request
from one_ring_http.response import Response
from one_ring_http.websocket import WebSocket
from one_ring_loop.typedefs import Coro

type HTTPHeaders = dict[str, str]

type HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]

type SyncHTTPHandler = Callable[[Request], Response]
type AsyncHTTPHandler = Callable[[Request], Coro[Response]]
type HTTPHandler = SyncHTTPHandler | AsyncHTTPHandler
type HTTPMiddleware = Callable[[AsyncHTTPHandler], AsyncHTTPHandler]

type WebSocketHandler = Callable[[WebSocket], Coro[None]]
