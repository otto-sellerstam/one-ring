from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from one_ring_http.log import get_logger
from one_ring_http.response import Response
from one_ring_loop.fileio import open_file  # or however your file I/O is exposed

if TYPE_CHECKING:
    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler
    from one_ring_loop.typedefs import Coro

logger = get_logger()


def static_handler(root: str | Path) -> HTTPHandler:
    """Returns a handler that serves files from root directory."""
    root_path = Path(root).resolve()

    def handler(request: Request) -> Coro[Response]:
        path = request.path
        if path == "/":
            path = "/index.html"

        candidates = [
            root_path / path.lstrip("/"),
            root_path / (path.lstrip("/") + ".html"),
            root_path / path.lstrip("/") / "index.html",
        ]

        for candidate in candidates:
            # Resolve and check it's still under root
            file_path = candidate.resolve()
            if not file_path.is_relative_to(root_path):
                continue
            try:
                file = yield from open_file(file_path)
            except FileNotFoundError:
                continue

            try:
                body = yield from file.read()
                content_type = (
                    mimetypes.guess_type(str(file_path))[0]
                    or "application/octet-stream"
                )
            finally:
                yield from file.close()

            return Response(
                status_code=200,
                headers={"content-type": content_type},
                body=body.encode(),
            )

        return Response(status_code=404, body=b"Not Found")

    return handler
