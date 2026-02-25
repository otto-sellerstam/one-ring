from enum import IntEnum


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
