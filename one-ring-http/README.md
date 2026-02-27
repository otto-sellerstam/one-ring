# one-ring-http

HTTP/1.1 server built on [one-ring-loop](https://pypi.org/project/one-ring-loop/) and Linux io_uring.

Part of the [one-ring](https://github.com/otto-sellerstam/one-ring) project.

## What it provides

- **HTTPServer** - TLS-enabled HTTP/1.1 server
- **Router** - method + path routing with fallback handlers
- **Request/Response** - parsed HTTP requests, serializable responses
- **Static file serving** - built-in static file handler

## Example

```python
import ssl

from one_ring_http.response import Response
from one_ring_http.router import Router
from one_ring_http.server import HTTPServer
from one_ring_loop import run

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("cert.pem", "key.pem")

def hello(request):
    return Response(status_code=200, body=b"Hello, world!")

router = Router()
router.add("GET", "/", hello)

server = HTTPServer(router=router, host="127.0.0.1", port=8000, ssl_context=ssl_context)
run(server.serve())
```

## Requirements

- **Linux** with io_uring support (kernel 6.7+)
- **Python 3.14+**

## Installation

```bash
uv add one-ring-http
```

## License

MIT
