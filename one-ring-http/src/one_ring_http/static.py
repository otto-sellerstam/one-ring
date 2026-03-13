from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from one_ring_http.log import get_logger
from one_ring_http.response import Response
from one_ring_http.status import HTTPStatus
from one_ring_loop.fileio import (
    open_file,
    statx,
)

if TYPE_CHECKING:
    from one_ring_http.request import Request
    from one_ring_http.typedef import HTTPHandler
    from one_ring_loop.typedefs import Coro

logger = get_logger()


def get_candidates(root_path: Path, path: str) -> list[Path]:
    """Determines the potential candidates that a request path should get."""
    return [
        root_path / path.lstrip("/"),
        root_path / (path.lstrip("/") + ".html"),
        root_path / path.lstrip("/") / "index.html",
    ]


def static_handler(root: str | Path) -> HTTPHandler:
    """Returns a handler that serves files from root directory."""
    root_path = Path(root).resolve()

    def get_file_response(request: Request, file_path: Path) -> Coro[Response]:
        # Create ETag from file metadata for browser caching support.
        metadata = yield from statx(file_path)
        etag = f'"{metadata.ino:x}-{metadata.mtime_sec}"'

        # Check if the browser can use a cached response.
        if (
            browser_etag := request.headers.get("if-none-match")
        ) is not None and browser_etag == etag:
            return Response(status_code=HTTPStatus.NOT_MODIFIED, headers={"etag": etag})

        # Browser cache didn't match. Normal response with body.
        file = yield from open_file(file_path)

        try:
            body = yield from file.read()
            content_type = (
                mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            )
        finally:
            yield from file.close()

        return Response(
            status_code=HTTPStatus.OK,
            headers={"content-type": content_type, "etag": etag},
            body=body,
        )

    def handler(request: Request) -> Coro[Response]:
        path = request.path
        if path == "/":
            path = "/index.html"

        candidates = get_candidates(root_path, path)

        for candidate in candidates:
            # Resolve and check it's still under root.
            file_path = candidate.resolve()
            if not file_path.is_relative_to(root_path):
                continue

            try:
                response = yield from get_file_response(request, file_path)
            except FileNotFoundError, OSError:
                continue

            return response

        return Response(status_code=HTTPStatus.NOT_FOUND, body=b"Not Found")

    return handler
