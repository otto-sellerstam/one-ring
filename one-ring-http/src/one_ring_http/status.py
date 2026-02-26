from enum import IntEnum


class HTTPStatus(IntEnum):
    """HTTP status codes with reason phrases."""

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    MOVED_PERMANENTLY = 301
    FOUND = 302
    NOT_MODIFIED = 304
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    GONE = 410
    TEAPOT = 418
    TOO_MANY_REQUESTS = 429

    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

    @property
    def phrase(self) -> str:
        """Gets the corresponding reason phrase."""
        return _PHRASES[self]


_PHRASES: dict[HTTPStatus, str] = {
    HTTPStatus.OK: "OK",
    HTTPStatus.CREATED: "Created",
    HTTPStatus.ACCEPTED: "Accepted",
    HTTPStatus.NO_CONTENT: "No Content",
    HTTPStatus.MOVED_PERMANENTLY: "Moved Permanently",
    HTTPStatus.FOUND: "Found",
    HTTPStatus.NOT_MODIFIED: "Not Modified",
    HTTPStatus.TEMPORARY_REDIRECT: "Temporary Redirect",
    HTTPStatus.PERMANENT_REDIRECT: "Permanent Redirect",
    HTTPStatus.BAD_REQUEST: "Bad Request",
    HTTPStatus.UNAUTHORIZED: "Unauthorized",
    HTTPStatus.FORBIDDEN: "Forbidden",
    HTTPStatus.NOT_FOUND: "Not Found",
    HTTPStatus.METHOD_NOT_ALLOWED: "Method Not Allowed",
    HTTPStatus.CONFLICT: "Conflict",
    HTTPStatus.GONE: "Gone",
    HTTPStatus.TEAPOT: "I'm a Teapot",
    HTTPStatus.TOO_MANY_REQUESTS: "Too Many Requests",
    HTTPStatus.INTERNAL_SERVER_ERROR: "Internal Server Error",
    HTTPStatus.NOT_IMPLEMENTED: "Not Implemented",
    HTTPStatus.BAD_GATEWAY: "Bad Gateway",
    HTTPStatus.SERVICE_UNAVAILABLE: "Service Unavailable",
    HTTPStatus.GATEWAY_TIMEOUT: "Gateway Timeout",
}
