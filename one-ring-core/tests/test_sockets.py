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
            w.register(SocketSetOpt(server_fd), 2)
            w.register(SocketBind(server_fd, b"127.0.0.1", 9999), 3)
            w.submit()
            w.wait()
            w.wait()

            w.register(SocketListen(server_fd), 4)
            w.submit()
            w.wait()

            # === Client setup ===
            w.register(SocketCreate(), 5)
            w.submit()
            client_fd = w.wait().unwrap().fd  # pyrefly: ignore

            # Accept client
            w.register(SocketAccept(server_fd), 6)
            w.register(SocketConnect(client_fd, b"127.0.0.1", 9999), 7)
            w.submit()  # one syscall, kernel handles both

            # Two completions come back (order may vary)
            c1 = w.wait()
            c2 = w.wait()

            accepted_fd = (
                (c1 if c1.user_data == 6 else c2).unwrap().fd  # pyrefly: ignore
            )

            # === Echo: client sends, server receives ===
            w.register(SocketSend(client_fd, b"hello"), 8)
            w.register(SocketRecv(accepted_fd, 1024), 9)
            w.submit()

            # Again, two completions
            w.wait()
            w.wait()
        finally:
            if server_fd:
                w.register(Close(server_fd), 1)
                w.submit()
                w.wait()
            if client_fd:
                w.register(Close(client_fd), 2)
                w.submit()
                w.wait()
            if accepted_fd:
                w.register(Close(accepted_fd), 3)
                w.submit()
                w.wait()
