# one-ring-core

Low-level [io_uring](https://kernel.dk/io_uring.pdf) wrapper for Python.

Part of the [one-ring](https://github.com/otto-sellerstam/one-ring) project.

## What it provides

- **Ring management** - initialize, submit, and consume io_uring submission/completion queues
- **Typed IO operations** - file open/read/write/close, socket create/bind/listen/accept/send/recv, timeouts
- **Result types** - structured completion events with user data, result codes, and flags

## Requirements

- **Linux** with `io_uring` support (kernel 6.7+ for full socket support)
- **Python 3.14+**

## Installation

```bash
uv add one-ring-core
```

## License

MIT
