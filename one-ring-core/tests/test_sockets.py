from one_ring_core.operations import (
    Close,
    SocketAccept,
    SocketBind,
    SocketConnect,
    SocketCreate,
    SocketListen,
    SocketRecv,
    SocketSend,
    SocketSetOpt,
)
from one_ring_core.worker import IOWorker


def test_sockets() -> None:
    server_fd: int | None = None
    client_fd: int | None = None
    accepted_fd: int | None = None

    with IOWorker() as w:
        # Create socket
        w.register(SocketCreate(), 1)
        w.submit()
        server_fd = w.wait().unwrap().fd  # pyrefly: ignore

        try:
            # Set reuse addr + bind + listen
            w.register(SocketSetOpt(fd=server_fd), 2)
            w.register(SocketBind(fd=server_fd, ip=b"127.0.0.1", port=9999), 3)
            w.submit()
            w.wait()
            w.wait()

            w.register(SocketListen(fd=server_fd), 4)
            w.submit()
            w.wait()

            # === Client setup ===
            w.register(SocketCreate(), 5)
            w.submit()
            client_fd = w.wait().unwrap().fd  # pyrefly: ignore

            # Accept client
            w.register(SocketAccept(fd=server_fd), 6)
            w.register(SocketConnect(fd=client_fd, ip=b"127.0.0.1", port=9999), 7)
            w.submit()  # one syscall, kernel handles both

            # Two completions come back (order may vary)
            c1 = w.wait()
            c2 = w.wait()

            accepted_fd = (
                (c1 if c1.user_data == 6 else c2).unwrap().fd  # pyrefly: ignore
            )

            # === Echo: client sends, server receives ===
            w.register(SocketSend(fd=client_fd, data=b"hello"), 8)
            w.register(SocketRecv(fd=accepted_fd, size=1024), 9)
            w.submit()

            # Again, two completions
            w.wait()
            w.wait()
        finally:
            if server_fd:
                w.register(Close(fd=server_fd), 1)
                w.submit()
                w.wait()
            if client_fd:
                w.register(Close(fd=client_fd), 2)
                w.submit()
                w.wait()
            if accepted_fd:
                w.register(Close(fd=accepted_fd), 3)
                w.submit()
                w.wait()
