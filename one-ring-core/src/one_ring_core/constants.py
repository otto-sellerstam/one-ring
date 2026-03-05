"""Typed constants for io_uring operations.

Re-exports raw values from rusty_ring as IntEnum/IntFlag classes.
"""

from enum import IntEnum, IntFlag

from rusty_ring import (
    AF_INET,
    AF_INET6,
    AF_UNIX,
    AT_EMPTY_PATH,
    AT_FDCWD,
    AT_SYMLINK_NOFOLLOW,
    IPPROTO_TCP,
    MSG_DONTWAIT,
    MSG_NOSIGNAL,
    O_APPEND,
    O_CLOEXEC,
    O_CREAT,
    O_NONBLOCK,
    O_RDONLY,
    O_RDWR,
    O_TRUNC,
    O_WRONLY,
    S_IFDIR,
    S_IFIFO,
    S_IFLNK,
    S_IFMT,
    S_IFREG,
    S_IFSOCK,
    S_IRGRP,
    S_IROTH,
    S_IRUSR,
    S_IWGRP,
    S_IWOTH,
    S_IWUSR,
    S_IXGRP,
    S_IXOTH,
    S_IXUSR,
    SFD_CLOEXEC,
    SFD_NONBLOCK,
    SIGHUP,
    SIGINT,
    SIGTERM,
    SO_KEEPALIVE,
    SO_REUSEADDR,
    SO_REUSEPORT,
    SOCK_CLOEXEC,
    SOCK_DGRAM,
    SOCK_NONBLOCK,
    SOCK_STREAM,
    SOL_SOCKET,
    STATX_ALL,
    STATX_ATIME,
    STATX_CTIME,
    STATX_INO,
    STATX_MODE,
    STATX_MTIME,
    STATX_SIZE,
    STATX_TYPE,
    TCP_NODELAY,
)


class OpenFlags(IntFlag):
    """Flags for file open operations (openat)."""

    RDONLY = O_RDONLY
    WRONLY = O_WRONLY
    RDWR = O_RDWR
    CREAT = O_CREAT
    TRUNC = O_TRUNC
    APPEND = O_APPEND
    NONBLOCK = O_NONBLOCK
    CLOEXEC = O_CLOEXEC


class FileMode(IntFlag):
    """File permission bits for open with O_CREAT."""

    # Owner
    OWNER_READ = S_IRUSR
    OWNER_WRITE = S_IWUSR
    OWNER_EXEC = S_IXUSR
    # Group
    GROUP_READ = S_IRGRP
    GROUP_WRITE = S_IWGRP
    GROUP_EXEC = S_IXGRP
    # Other
    OTHER_READ = S_IROTH
    OTHER_WRITE = S_IWOTH
    OTHER_EXEC = S_IXOTH

    # Common combinations
    RW_OWNER = S_IRUSR | S_IWUSR
    RW_OWNER_R_GROUP = S_IRUSR | S_IWUSR | S_IRGRP
    RW_OWNER_R_ALL = S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH
    RWXU_RX_ALL = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH


class FileType(IntFlag):
    """File type bits extracted from mode (stx_mode & S_IFMT)."""

    REGULAR = S_IFREG
    DIRECTORY = S_IFDIR
    SYMLINK = S_IFLNK
    SOCKET = S_IFSOCK
    FIFO = S_IFIFO
    MASK = S_IFMT


class AtFlags(IntFlag):
    """Flags for path resolution (statx, openat, etc.)."""

    FDCWD = AT_FDCWD
    EMPTY_PATH = AT_EMPTY_PATH
    SYMLINK_NOFOLLOW = AT_SYMLINK_NOFOLLOW


class StatxMask(IntFlag):
    """Mask for which statx fields to populate."""

    TYPE = STATX_TYPE
    MODE = STATX_MODE
    INO = STATX_INO
    SIZE = STATX_SIZE
    MTIME = STATX_MTIME
    ATIME = STATX_ATIME
    CTIME = STATX_CTIME
    ALL = STATX_ALL

    # Common combinations
    FILE_INFO = STATX_SIZE | STATX_MTIME | STATX_INO


class AddressFamily(IntEnum):
    """Socket address families."""

    INET = AF_INET
    INET6 = AF_INET6
    UNIX = AF_UNIX


class SockType(IntFlag):
    """Socket types (can be OR'd with NONBLOCK/CLOEXEC)."""

    STREAM = SOCK_STREAM
    DGRAM = SOCK_DGRAM
    NONBLOCK = SOCK_NONBLOCK
    CLOEXEC = SOCK_CLOEXEC


class SockOptLevel(IntEnum):
    """Socket option levels."""

    SOCKET = SOL_SOCKET
    TCP = IPPROTO_TCP


class SockOpt(IntEnum):
    """Socket options."""

    REUSEADDR = SO_REUSEADDR
    REUSEPORT = SO_REUSEPORT
    KEEPALIVE = SO_KEEPALIVE
    TCP_NODELAY = TCP_NODELAY


class MsgFlags(IntFlag):
    """Flags for send/recv operations."""

    NOSIGNAL = MSG_NOSIGNAL
    DONTWAIT = MSG_DONTWAIT


class Signal(IntEnum):
    """Signal numbers."""

    INT = SIGINT
    TERM = SIGTERM
    HUP = SIGHUP


class SignalfdFlags(IntFlag):
    """Flags for signalfd creation."""

    NONBLOCK = SFD_NONBLOCK
    CLOEXEC = SFD_CLOEXEC
