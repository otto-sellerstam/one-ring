# one-ring

Generator based async I/O from scratch using Linux's `io_uring`, a custom event loop, and (soon) an asyncio integration layer.

## Packages

- **one-ring-core** — Low-level `io_uring` wrapper: ring management, IO operations, and result types
- **one-ring-loop** — Custom event loop with task scheduling, file I/O, socket I/O, and timers
- **one-ring-asyncio** — asyncio event loop integration (WIP)

## Example

An echo server built on `one-ring-loop`. See source [here](examples/echo_server.py).

Run it and connect via `ncat`!

```python
from typing import TYPE_CHECKING

from one_ring_loop.loop import create_task, run
from one_ring_loop.socketio import Connection, create_server

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def echo_handler(conn: Connection) -> Coro[None]:
    """Gets data sent from a client and echoes it."""
    try:
        while True:
            data = yield from conn.recv(1024)
            if not data:
                break
            yield from conn.send(data)
    finally:
        yield from conn.close()


def echo_server() -> Coro[None]:
    """Echo server entrypoint."""
    server = yield from create_server(b"0.0.0.0", 9999)
    try:
        while True:
            conn = yield from server.accept()
            create_task(echo_handler(conn))
    finally:
        yield from server.close()


if __name__ == "__main__":
    run(echo_server())
```

## Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (task runner)
# macOS:
brew install just
# Linux:
cargo install just # (or see https://github.com/casey/just#installation)

# First-time setup (install deps + pre-commit hooks)
just setup
```

## Development

```bash
just check             # Run all checks across all packages
just test-pkg <name>   # Test a single package
just lint-fix          # Auto-fix linting issues
just format            # Auto-format code
just test-cov          # Run tests with coverage (all packages)
```

Run `just` to see all available commands.

## Tools

| Tool | Purpose |
|------|---------|
| [uv](https://docs.astral.sh/uv/) | Package & environment management (workspaces) |
| [Ruff](https://docs.astral.sh/ruff/) | Linting & formatting |
| [Pyrefly](https://pyrefly.org/) | Type checking |
| [Pytest](https://docs.pytest.org/) | Testing |
| [Just](https://github.com/casey/just) | Task runner |
| [Pre-commit](https://pre-commit.com/) | Git hooks |
