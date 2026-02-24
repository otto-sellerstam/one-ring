from collections.abc import Callable
from typing import Literal

from one_ring_http.request import Request
from one_ring_http.response import Response
from one_ring_loop.typedefs import Coro

type HTTPHeaders = dict[str, str]

type HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]

type HTTPHandler = Callable[[Request], Coro[Response] | Response]
