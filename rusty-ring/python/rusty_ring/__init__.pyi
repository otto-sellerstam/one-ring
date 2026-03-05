import types
from typing import Self

class SockAddr:
    @staticmethod
    def v4(ip: str, port: int) -> SockAddr: ...
    @staticmethod
    def v6(ip: str, port: int) -> SockAddr: ...

class CompletionEvent:
    @property
    def user_data(self) -> int: ...
    @property
    def res(self) -> int: ...
    @property
    def flags(self) -> int: ...

class Ring:
    def __init__(self, depth: int = 32) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool: ...
    def submit(self) -> int: ...
    def peek(self) -> CompletionEvent | None: ...
    def wait(self) -> CompletionEvent: ...
    def prep_nop(self, user_data: int) -> None: ...
    def prep_timeout(self, user_data: int, sec: int, nsec: int) -> None: ...
    def prep_close(
        self,
        user_data: int,
        fd: int,
    ) -> None: ...
    def prep_cancel(
        self, user_data: int, target_user_data: int, flags: int = 0
    ) -> None: ...
    def prep_read(
        self, user_data: int, fd: int, buf: bytearray, nbytes: int, offset: int
    ) -> None: ...
    def prep_write(self, user_data: int, fd: int, buf: bytes, offset: int) -> None: ...
    def prep_openat(
        self, user_data: int, path: str, flags: int, mode: int, dir_fd: int
    ) -> None: ...
    def prep_statx(
        self,
        user_data: int,
        path: str,
        buf: StatxBuffer,
        flags: int,
        mask: int,
        dir_fd: int,
    ) -> None: ...
    def prep_socket(
        self,
        user_data: int,
        domain: int,
        sock_type: int,
        protocol: int = 0,
        flags: int = 0,
    ) -> None: ...
    def prep_socket_setopt(
        self,
        user_data: int,
        fd: int,
    ) -> None: ...
    def prep_socket_bind(
        self, user_data: int, fd: int, sock_addr: SockAddr
    ) -> None: ...
    def prep_socket_listen(self, user_data: int, fd: int, backlog: int) -> None: ...
    def prep_socket_accept(self, user_data: int, fd: int) -> None: ...
    def prep_socket_recv(
        self, user_data: int, fd: int, buf: bytearray, flags: int = 0
    ) -> None: ...
    def prep_socket_send(
        self, user_data: int, fd: int, buf: bytes, flags: int = 0
    ) -> None: ...
    def prep_socket_connect(
        self, user_data: int, fd: int, sock_addr: SockAddr
    ) -> None: ...

class StatxBuffer:
    def __init__(self) -> None: ...
    @property
    def size(self) -> int: ...
    @property
    def mtime_sec(self) -> int: ...
    @property
    def ino(self) -> int: ...
    @property
    def mode(self) -> int: ...

# File open flags
O_RDONLY: int
O_WRONLY: int
O_RDWR: int
O_CREAT: int
O_TRUNC: int
O_APPEND: int
O_NONBLOCK: int
O_CLOEXEC: int

# File mode bits (permissions)
S_IRUSR: int
S_IWUSR: int
S_IXUSR: int
S_IRGRP: int
S_IWGRP: int
S_IXGRP: int
S_IROTH: int
S_IWOTH: int
S_IXOTH: int

# File type bits
S_IFREG: int
S_IFDIR: int
S_IFLNK: int
S_IFSOCK: int
S_IFIFO: int
S_IFMT: int

# AT flags (path resolution)
AT_FDCWD: int
AT_EMPTY_PATH: int
AT_SYMLINK_NOFOLLOW: int

# Statx mask
STATX_TYPE: int
STATX_MODE: int
STATX_INO: int
STATX_SIZE: int
STATX_MTIME: int
STATX_ATIME: int
STATX_CTIME: int
STATX_ALL: int

# Socket: address families
AF_INET: int
AF_INET6: int
AF_UNIX: int

# Socket: types
SOCK_STREAM: int
SOCK_DGRAM: int
SOCK_NONBLOCK: int
SOCK_CLOEXEC: int

# Socket: options
SOL_SOCKET: int
SO_REUSEADDR: int
SO_REUSEPORT: int
SO_KEEPALIVE: int
IPPROTO_TCP: int
TCP_NODELAY: int

# Socket: send/recv flags
MSG_NOSIGNAL: int
MSG_DONTWAIT: int

# Signals
SIGINT: int
SIGTERM: int
SIGHUP: int

# Signalfd flags
SFD_NONBLOCK: int
SFD_CLOEXEC: int
