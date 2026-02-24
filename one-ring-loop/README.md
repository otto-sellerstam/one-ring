# one-ring-loop

Custom async event loop built on [one-ring-core](https://pypi.org/project/one-ring-core/) and Linux io_uring.

Part of the [one-ring](https://github.com/otto-sellerstam/one-ring) project.

## What it provides

- **Task scheduling** with `Task` and `TaskGroup` (structured concurrency)
- **File IO** - async file operations via io_uring
- **Socket IO** - TCP server/client with `create_server`, `Connection.receive`/`send`
- **Timers** - async `sleep` backed by io_uring timeouts
- **Streams** - buffered byte streams, TLS wrapping, memory streams
- **Cancellation** - `move_on_after`/`fail_after` scoped timeout/cancellation

## Example

```python
from one_ring_loop import TaskGroup, run
from one_ring_loop.socketio import Connection, create_server

def echo_handler(conn):
    try:
        while True:
            data = yield from conn.receive(1024)
            if not data:
                break
            yield from conn.send(b"Echo: " + data)
    finally:
        yield from conn.close()

def main():
    server = yield from create_server(b"0.0.0.0", 9999)
    tg = TaskGroup()
    tg.enter()
    try:
        while True:
            conn = yield from server.accept()
            tg.create_task(echo_handler(conn))
    finally:
        yield from tg.exit()
        yield from server.close()

run(main())
```

## Requirements

- **Linux** with io_uring support (kernel 6.7+)
- **Python 3.14+**

## Installation

```bash
uv add one-ring-loop
```

**Note:** This package transitively requires `liburing >= 2025.8.26` (via one-ring-core),
which is not yet published to PyPI. Until it is, install liburing from GitHub first:

```bash
uv add git+https://github.com/YoSTEALTH/Liburing.git
```

## License

MIT
