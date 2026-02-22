class ClosedResourceError(Exception):
    """Thrown when the relevant stream has been closed."""


class BrokenResourceError(Exception):
    """Thrown when opposite end of stream has been closed."""


class EndOfStreamError(Exception):
    """Thrown when receive stream buffer is empty and send stream is closed."""


class DelimiterNotFoundError(Exception):
    """Raised if delimiter is not found within the max read."""
