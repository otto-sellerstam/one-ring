# Python io_uring Library — Project Plan

## Overview

Build a Python library that provides truly asynchronous file IO by leveraging Linux's `io_uring` kernel interface. Unlike existing libraries like `aiofiles` (which fake async by running synchronous IO in thread pools), this library uses kernel-level async IO with zero thread overhead.

The project is split into three packages:

- **`one-ring-core`** — Python bindings to io_uring. Pure plumbing: submit SQEs, collect CQEs, no event loop opinions. Initially uses the existing `liburing` Cython package, later replaced with custom FFI bindings.
- **`one-ring-loop`** — A hand-rolled event loop built from scratch using generators (not native `async/await`). Includes your own Future, Task, and scheduler. This is where you learn what asyncio actually does by building it yourself.
- **`one-ring-asyncio`** — A bridge that integrates `one-ring-core` with Python's real `asyncio` event loop via `eventfd` + `loop.add_reader()`.

Phases 1-7 cover the file IO library. Phases 8-10 extend it into network IO, culminating in an HTTP static file server built from the Linux kernel interface up.

---

## Phase 0: Environment Setup

### Verify io_uring Works

io_uring may already work on your stock WSL2 kernel (it does as of early 2026). Test first before doing anything else.

Install liburing and a compiler in your WSL distro:

```bash
sudo apt install liburing-dev gcc
```

Write and compile a minimal C program that initializes an io_uring instance:

```c
#include <liburing.h>
#include <stdio.h>

int main() {
    struct io_uring ring;
    int ret = io_uring_queue_init(32, &ring, 0);
    if (ret < 0) {
        printf("io_uring init failed: %d\n", ret);
        return 1;
    }
    printf("io_uring works!\n");
    io_uring_queue_exit(&ring);
    return 0;
}
```

Compile with `gcc -o test_uring test_uring.c -luring` and run `./test_uring`. If it prints "io_uring works!" — you're done with Phase 0.

### If io_uring is NOT Available

If the test fails, you need to compile a custom WSL2 kernel with `CONFIG_IO_URING=y` enabled. This involves cloning the WSL2 kernel source, enabling the config flag, building the kernel, and pointing WSL at it via `.wslconfig`. Full instructions: https://boxofcables.dev/how-to-build-a-custom-kernel-for-wsl-in-2025/

The key addition to those instructions is enabling io_uring: after copying the default config, either use `make menuconfig` (search for `IO_URING` with `/`) or edit `.config` directly and set `CONFIG_IO_URING=y`.

---

## Phase 1: Understand io_uring and Get It Working from C

### Research

Read the **Lord of the io_uring** guide: https://unixism.net/loti/

Focus on:
- The evolution from `select` → `poll` → `epoll` → `io_uring` and the limitations of each
- The **readiness model** (epoll: "this fd is ready, now you call read") vs the **completion model** (io_uring: "I submitted a read, kernel tells me when it's done")
- The submission queue (SQ) / completion queue (CQ) ring buffer architecture
- Shared memory between kernel and userspace — why this avoids syscall overhead
- The three operating modes: interrupt-driven, polled, kernel-polled
- liburing's higher-level C API vs the raw syscall interface
- **`user_data`** — when you submit an SQE, you can tag it with an arbitrary value in the `user_data` field. When the completion (CQE) arrives, it carries that same `user_data` back. This is how you know *which* submission just completed. This concept becomes critical in Phases 3-4 when you need to map completions to your Future objects.

### Implement

Work through the companion examples: https://github.com/shuveb/io_uring-by-example

These build progressively:
1. `01_regular_cat` — synchronous IO baseline
2. `02_cat_uring` — raw io_uring syscall interface
3. `03_cat_liburing` — same thing but with the liburing helper library
4. `04_cp_liburing` — multi-request copy (multiple SQEs in flight)
5. `05_webserver_liburing` — a web server using io_uring (you'll come back to this in Phases 8-10)

Write these yourself, don't just read them. You want the SQ/CQ model in your muscle memory.

The Lord of the io_uring guide also has its own example code repo: https://github.com/shuveb/loti-examples

### Supplementary resources
- io_uring and networking in 2023 (liburing wiki): https://github.com/axboe/liburing/wiki/io_uring-and-networking-in-2023
- awesome-iouring curated list: https://github.com/espoal/awesome-iouring
- Lord of the io_uring companion code (separate from io_uring-by-example): https://github.com/shuveb/loti-examples — includes code for eventfd registration, fixed buffers, SQ polling, and a web server

---

## Phase 2: Prove the Python ↔ io_uring Plumbing (`one-ring-core`)

### Research

Familiarize yourself with the `liburing` Python/Cython package:
- PyPI: https://pypi.org/project/liburing/
- Read its examples — particularly the `open_write_read_close.py` example
- Understand the mapping: which Python calls correspond to which C liburing functions you used in Phase 1?

You don't need to understand *how* the Cython bindings work yet — just the API surface.

### Implement

Get io_uring working from Python, without any async/await yet.

- `pip install liburing`
- From Python: open a file via io_uring, submit a read SQE, wait for the CQE, get the data back
- This is purely synchronous and blocking — you're just proving that Python can talk to io_uring
- Try submitting multiple SQEs before waiting, to exercise batching

The goal is confidence that the plumbing works before adding the async complexity. This code lives in `one-ring-core`.

---

## Phase 3: Build Your Own Event Loop (`one-ring-loop`)

This is the most educational phase of the entire project. Instead of jumping straight to asyncio, you build a working event loop from scratch — using generators, not native `async/await`. This forces you to understand everything that asyncio hides behind syntax sugar.

### Research

**Step 1: Understand generators as coroutines.**

Python generators aren't just for iteration — they're the foundation that `async/await` was built on. The key primitives:
- `yield` — suspend execution, return a value to the caller
- `gen.send(value)` — resume a suspended generator, injecting a value
- `gen.throw(exc)` — resume by raising an exception inside the generator
- `yield from` (PEP 380) — delegate to a sub-generator, transparently forwarding `send()` and `throw()`

Read PEP 342 (Coroutines via Enhanced Generators) to understand how `send()` and `throw()` turned generators into coroutines.

**Step 2: Study how others have built event loops from generators.**

David Beazley's work is the gold standard here:
- **"A Curious Course on Coroutines and Concurrency"** (2009) — the classic tutorial on building an OS-like scheduler from generators: http://dabeaz.com/coroutines/
- **"Build Your Own Async"** — a live-coded talk where he builds an event loop from scratch

These will show you the patterns: a run loop that calls `send()` on generators, a `yield` that means "I'm waiting for something", and a scheduler that decides which generator to resume next.

**Step 3: Understand non-blocking completion checking.**

Before building the loop, understand how to use io_uring without blocking:
- `io_uring_peek_cqe` — check if a completion is ready *without* waiting (returns immediately)
- `io_uring_wait_cqe` — block until a completion is ready

Experiment with submitting a read, doing something else, then peeking to see if it's done.

### Implement

**Build these components yourself, in order:**

1. **Future** — a simple class representing a value that doesn't exist yet. It has a state (pending/resolved/failed), a result, callbacks to fire on resolution, and the ability to be `yield`-ed from a generator (so the generator suspends until the Future resolves).

2. **Task** — wraps a generator. Calls `send()` to advance it. When the generator yields a Future, the Task registers itself as a callback on that Future so it gets resumed when the Future resolves.

3. **The run loop** — the scheduler. In each iteration:
   - Check io_uring for completions (non-blocking peek)
   - For each CQE: use `user_data` to find the matching Future, resolve it
   - Run any Tasks that became ready (their Futures resolved)
   - If nothing is ready, block briefly on `io_uring_wait_cqe` with a timeout (or use `eventfd` + `select`/`poll`)
   - Repeat

4. **IO operations as generator functions** — e.g. a `read_file()` that submits an SQE, creates a Future tagged with the same `user_data`, yields that Future (suspending), and resumes with the result when the Future resolves.

**The user-facing code should look something like:**

```python
def read_and_print(path):
    data = yield from read_file(path, 1024)
    print(f"Got: {data}")

loop = OneRingLoop()
loop.create_task(read_and_print("test.txt"))
loop.create_task(read_and_print("other.txt"))
loop.run()
```

No `async`, no `await`, no `asyncio` — just generators, `yield from`, and your own scheduler. Two file reads running concurrently through a single io_uring instance.

**What you'll learn:**
- What a Future actually *is* (a bookkeeping object, not magic)
- What a Task actually does (drives a generator forward)
- How an event loop *decides what to run next* (the scheduling problem)
- Why `async/await` exists (it's syntax sugar over exactly what you just built)
- How `user_data` connects the kernel's completion model to your Python-level scheduling

---

## Phase 4: Bridge io_uring to asyncio (`one-ring-asyncio`)

After building your own event loop, integrating with asyncio should feel almost anticlimactic — you already understand every concept involved.

### Research

**Step 1: Understand asyncio internals.**

Read the **actual CPython source code** for:
- `asyncio.SelectorEventLoop` — how the main loop iterates, how it calls `selector.select()`, how it schedules callbacks
- `selectors.EpollSelector` — how epoll is wrapped for Python
- `asyncio.Future` — how a future gets created, awaited, and resolved

Key questions to answer through reading:
- What does `loop.add_reader(fd, callback)` actually do under the hood?
- How does one iteration of `_run_once()` work?
- How would an `eventfd` file descriptor integrate with epoll?
- How does `loop.call_soon()` vs `loop.call_later()` interact with the selector?

Compare what you find to the event loop you built in Phase 3. You'll recognize the same patterns — asyncio's `Future` is your Future, asyncio's `Task` is your Task, `_run_once()` is your run loop iteration.

**Step 2: Study existing solutions.**

Look at how existing projects solved this same problem:
- `aioring` (https://pypi.org/project/aioring/) — API design, fallback strategy for non-Linux
- `uring_file` (https://github.com/qweeze/uring_file) — minimal asyncio integration
- `kloop` (https://github.com/fantix/kloop) — full event loop replacement approach
- Rust's `tokio-uring` — different language, same architectural problem

Don't copy these. Study the *choices* they made and ask yourself why.

### Implement

**Integrate with asyncio:**
- Create an `eventfd` and register it with the io_uring instance (so the kernel writes to it on completions)
- Register that `eventfd` with asyncio's event loop via `loop.add_reader(eventfd, callback)`
- In the callback: drain the completion queue, use `user_data` from each CQE to look up the corresponding asyncio `Future`, and resolve it
- Now `await`-ing a future should properly suspend the coroutine, let other work run, and resume on completion

**Critical gotcha:** an eventfd notification is only a *hint* that completions are available. Multiple CQEs might produce only a single eventfd notification. Your callback must drain *all* available CQEs in a loop, not just read one — otherwise completions will silently get stuck.

The Lord of the io_uring guide has a dedicated tutorial on registering an eventfd: https://unixism.net/loti/tutorial/register_eventfd.html — read this before implementing.

**The `user_data` → `Future` mapping is the core design problem.** When you submit an SQE, you assign it a `user_data` value and store a `Future` keyed by that value. When a CQE arrives, you read its `user_data`, find the matching `Future`, and call `future.set_result()` with the result. This is what connects io_uring's completion model to Python's async/await. You already solved this exact problem in Phase 3 with your own Futures — now you're just doing it with asyncio's.

Test with a simple script: read a file with `await`, and prove that other coroutines actually run concurrently while the IO is in flight.

---

## Phase 5: Build the API

### Research

Look at the APIs of:
- Python's built-in `open()` / file objects — what interface do users expect?
- `aiofiles` — the de facto async file IO library, even though it fakes it with threads
- `aioring` — how they structured their async file API

Think about: context managers, error handling patterns, what operations to support.

### Implement

Design and build a Pythonic interface:

```python
from your_lib import aio

async with aio.open("data.txt", "r") as f:
    content = await f.read()

async with aio.open("output.txt", "w") as f:
    await f.write("hello world")
```

**Start with unbuffered operations only:**
- `read(nbytes)` — read a specific number of bytes at an offset
- `write(data)` — write bytes at an offset
- `open()` / `close()` — file lifecycle
- `fsync()` — flush to disk
- Context managers (`async with`) for resource cleanup

**Buffered operations (like `readline()`) are a stretch goal.** io_uring operates at the level of raw byte reads at specific offsets — it has no concept of "lines." Implementing `readline()` means managing your own read-ahead buffer, scanning for newlines, handling lines that span multiple kernel reads, etc. It's a real design problem. Get the unbuffered API solid first.

Other considerations:
- Proper error propagation (kernel errors → Python exceptions)
- Type hints throughout
- What additional operations to support later: stat, readv/writev

---

## Phase 6: Harden and Benchmark

### Research

Look into common io_uring pitfalls:
- What happens when the submission queue is full?
- How do partial reads/writes behave?
- What are the `IOSQE_IO_LINK` semantics for chained operations?

### Implement

- Handle edge cases: SQ full, partial reads/writes, interrupted operations
- Write tests (actual file IO tests, not mocks)
- Benchmark against `aiofiles` (thread pool) and synchronous IO

**Setting expectations for benchmarks:** For a single file read, io_uring probably won't dramatically beat a thread pool — the actual disk IO time dominates regardless of how you submit it. The win shows up under **high concurrency** (many files read simultaneously) where the thread pool creates dozens of OS threads while io_uring handles it all with zero threads and fewer syscalls. If you benchmark a single sequential read and see no improvement, that's expected — not a sign something is wrong. Design your benchmarks to show the concurrency advantage:
- Read 100+ files concurrently
- Profile thread count and memory usage, not just wall-clock time
- Measure syscall count (using `strace -c`) to show the structural difference

---

## Phase 7: Replace the FFI Layer with Your Own Bindings (`one-ring-core`)

### Background: What is FFI?

FFI (Foreign Function Interface) is the general concept of calling code written in one language (typically C) from another (Python). The `liburing` Cython package you've been using is someone else's FFI layer. Now you build your own.

There are three main FFI mechanisms in Python:
- **ctypes** — pure Python, no compilation needed, but verbose and slower
- **cffi** (C Foreign Function Interface) — you paste C declarations into Python and call them directly. Cleaner than ctypes, no special language syntax
- **Cython** — a Python-like language that compiles to C. Best performance, but has its own syntax and build step

### Research

- Study the `liburing` Cython package source — see how it wraps the C API
- Look at `liburing-ffi.so` (https://github.com/axboe/liburing) — a shared library variant specifically designed for FFI consumption, which makes cffi a natural fit
- Try each FFI approach (ctypes, cffi, Cython) with a trivial C function to feel the tradeoffs

### Implement

**Why this phase works best last:**
- You know exactly which liburing functions your library calls — probably a small subset of the full API
- You understand the call patterns, buffer lifetimes, and performance-sensitive paths
- You have a working test suite to verify your new bindings produce identical behavior
- You're learning FFI *with context* rather than in the abstract

**Approach:**
- Audit your code: list every `liburing` function you call and every struct you touch
- Choose your FFI tool (cffi is a natural fit given `liburing-ffi.so`)
- Build bindings for just the functions you need — resist the urge to wrap the entire API
- Swap in your bindings, run your existing tests, benchmark to confirm no performance regression
- This phase doubles as a test of your architecture: if the replacement is painful, it reveals coupling that shouldn't be there

**What you'll learn:**
- Memory management at the C/Python boundary (who owns the buffer? when does it get freed?)
- How the GIL interacts with C calls (and when to release it)
- Build systems and packaging for native extensions

---

## Next Steps: Network IO and Building an HTTP Server

Once the file IO library is complete, the natural extension is network IO — io_uring handles sockets through the same SQ/CQ interface, using operations like `io_uring_prep_accept`, `io_uring_prep_recv`, and `io_uring_prep_send` instead of file read/write. Your event loops, `user_data` → `Future` mapping, and overall architecture all carry over directly.

### Phase 8: TCP Echo Server with io_uring

**Research:**
- How TCP sockets work at the syscall level: `socket()`, `bind()`, `listen()`, `accept()`, `recv()`, `send()`
- How io_uring replaces the traditional `epoll` + non-blocking sockets model for networking
- The io_uring networking guide: https://github.com/axboe/liburing/wiki/io_uring-and-networking-in-2023
- The Lord of the io_uring webserver tutorial: https://unixism.net/loti/tutorial/webserver_liburing.html
- The `05_webserver_liburing` example from Phase 1: https://github.com/shuveb/io_uring-by-example/tree/master/05_webserver_liburing

**Implement:**
- Build a TCP echo server: accept connections, read bytes, send them back
- Use io_uring for all socket operations (accept, recv, send) — no epoll, no threads
- Handle multiple concurrent connections through the same submission queue
- This is the networking equivalent of Phase 2 — proving the plumbing works

### Phase 9: HTTP/1.1 Request Parsing

**Research:**
- The HTTP/1.1 specification (RFC 9112) — at minimum, understand the request line (`GET /path HTTP/1.1\r\n`), headers (key-value pairs separated by `\r\n`), and the `\r\n\r\n` that terminates the header section
- How `Content-Length` and chunked transfer encoding determine where the body ends

**Implement:**
- Parse incoming bytes into HTTP requests (method, path, headers)
- You'll hit the same buffering challenge as `readline()` from Phase 5 — TCP delivers a stream of bytes with no message boundaries, so a single `recv` might contain half a request or two and a half requests. You need to buffer and scan for `\r\n\r\n`.
- Generate HTTP responses: status line, headers, body. A minimal "hello world" response is just a hardcoded string.

### Phase 10: Static File Server

**Research:**
- How HTTP `Content-Type` headers map to file extensions
- How `Content-Length` is used to signal body size

**Implement:**
- Combine both halves of the project: network IO to handle the HTTP connection, file IO to read files from disk — both through io_uring's single submission queue
- Serve static files from a directory based on the request path
- This is where io_uring's unified model pays off: a single event loop handling both disk reads and socket writes, with zero threads
- At this point you can legitimately say you built an HTTP server from the Linux kernel interface up

---

## Reference Projects

| Project | What to study | When to look at it |
|---|---|---|
| Lord of the io_uring | io_uring fundamentals | Phase 1 |
| io_uring-by-example | Hands-on C examples (includes webserver) | Phases 1, 8 |
| loti-examples | Companion code for Lord of the io_uring (eventfd, fixed buffers, etc.) | Phases 1, 4 |
| `liburing` (PyPI) | Python API over io_uring | Phase 2 |
| David Beazley's coroutine tutorials | Building schedulers from generators | Phase 3 |
| `aioring` | API design, asyncio integration | Phases 4-5 |
| `uring_file` | Minimal asyncio bridge | Phase 4 |
| `Shakti` | Python async/await interface over liburing | Phases 4-5 |
| `kloop` | Full event loop replacement | Phase 4 |
| `tokio-uring` (Rust) | Completion-based async runtime design | Phases 3-4 |
| `uvloop` | Non-standard IO backend + asyncio | Phase 4 |
| `aiofiles` | User-facing API expectations | Phase 5 |
| `liburing` (C, GitHub) | FFI-friendly shared library | Phase 7 |
| liburing networking wiki | io_uring socket operations | Phase 8 |
| RFC 9112 | HTTP/1.1 message syntax | Phase 9 |

---

## Key Concepts You'll Learn Along the Way

- **Readiness vs completion IO models** — the fundamental paradigm shift in io_uring (Phase 1)
- **Ring buffers and shared memory** — lock-free kernel/userspace communication (Phase 1)
- **`user_data` and completion tracking** — mapping kernel completions to application state (Phases 1, 3, 4)
- **Linux syscall mechanics** — how system calls work and why minimizing them matters (Phases 1-2)
- **Generators as coroutines** — `yield`, `send()`, `throw()`, and `yield from` as the foundation of async Python (Phase 3)
- **Event loop internals from first principles** — what a Future, Task, and scheduler actually are, built by hand (Phase 3)
- **Why `async/await` exists** — understanding the syntax sugar by having built the thing it sugars over (Phase 3)
- **asyncio event loop architecture** — moving from "implementer of your own" to "integrator with the standard one" (Phase 4)
- **epoll internals** — since you'll integrate with it via asyncio (Phase 4)
- **API design** — making low-level primitives feel Pythonic (Phase 5)
- **FFI and native extensions** — calling C from Python, memory ownership, GIL management (Phase 7)
- **Abstraction design** — your FFI migration will test whether your internal boundaries are clean (Phase 7)
- **TCP/IP socket programming** — how connections are established and data flows at the syscall level (Phase 8)
- **Protocol parsing** — turning a raw byte stream into structured HTTP messages (Phase 9)
- **Unified IO architecture** — using a single event loop for both disk and network IO (Phase 10)