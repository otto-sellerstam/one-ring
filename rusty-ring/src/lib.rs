use io_uring::{IoUring, opcode, types};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes};
use std::collections::HashMap;
use std::ffi::CString;
use std::net::{Ipv4Addr, Ipv6Addr};
use std::os::unix::io::RawFd;

/// A completed io_uring operation.
#[pyclass(frozen)]
#[derive(Clone, Debug)]
struct CompletionEvent {
    #[pyo3(get)]
    user_data: u64,
    #[pyo3(get)]
    res: i32,
    #[pyo3(get)]
    flags: u32,
}

#[pymethods]
impl CompletionEvent {
    fn __repr__(&self) -> String {
        format!(
            "CompletionEvent(user_data={}, res={}, flags={})",
            self.user_data, self.res, self.flags
        )
    }
}

#[allow(dead_code)]
struct StatxRequest {
    path: CString,
    statxbuf: Py<StatxBuffer>,
}

/// Owns an io_uring instance and exposes prep/submit/complete operations.
///
/// Usage from Python:
/// ```python
///     with Ring(depth=32) as ring:
///         ring.prep_nop(user_data=1)
///         ring.submit()
///         cqe = ring.wait()
/// ```
///
#[pyclass]
struct Ring {
    ring: Option<IoUring>,
    depth: u32,

    /// Buffers that are currently owned by the kernel (between submit and CQE).
    /// Keyed by `user_data` so they can be released when the CQE arrives.
    ///
    /// The kernel holds raw pointers into these buffers. They must be kept
    /// alive and un-resized until the corresponding CQE is consumed.
    /// TODO: Consolidate into 1.
    pinned_mutable_buffers: HashMap<u64, Py<PyByteArray>>,

    pinned_immutable_buffers: HashMap<u64, Py<PyBytes>>,

    /// CStrings for paths passed to openat.
    pinned_paths: HashMap<u64, CString>,

    /// Timespecs for timeouts.
    pinned_timespecs: HashMap<u64, types::Timespec>,

    /// Addresses for sockets.
    pinned_sockaddr: HashMap<u64, SockAddrInner>,

    /// Socket option values. Boxed for pointer stability across HashMap resizes.
    pinned_sockopts: HashMap<u64, Box<i32>>,

    // Statx buffers
    pinned_statx_buffers: HashMap<u64, StatxRequest>,
}

impl Ring {
    fn uring_mut(&mut self) -> PyResult<&mut IoUring> {
        self.ring
            .as_mut()
            .ok_or_else(|| PyRuntimeError::new_err("Ring not initialised (use as context manager)"))
    }

    /// Push an entry onto the SQ. Panics if SQ is full.
    fn push_entry(&mut self, entry: io_uring::squeue::Entry) -> PyResult<()> {
        let ring = self.uring_mut()?;
        // SAFETY: we trust that the caller has set up the entry correctly and
        // that any buffers referenced are pinned in `pinned_buffers`.
        unsafe {
            ring.submission()
                .push(&entry)
                .map_err(|_| PyRuntimeError::new_err("Submission queue is full"))?;
        }
        Ok(())
    }

    /// Release any pinned resources associated with a completed user_data.
    fn release_pinned(&mut self, user_data: u64) {
        self.pinned_mutable_buffers.remove(&user_data);
        self.pinned_immutable_buffers.remove(&user_data);
        self.pinned_paths.remove(&user_data);
        self.pinned_sockaddr.remove(&user_data);
        self.pinned_timespecs.remove(&user_data);
        self.pinned_sockopts.remove(&user_data);
        self.pinned_statx_buffers.remove(&user_data);
    }

    fn cqe_to_event(&mut self, cqe: &io_uring::cqueue::Entry) -> CompletionEvent {
        let user_data = cqe.user_data();
        self.release_pinned(user_data);
        CompletionEvent {
            user_data,
            res: cqe.result(),
            flags: cqe.flags(),
        }
    }
}

#[pymethods]
impl Ring {
    #[new]
    #[pyo3(signature = (depth = 32))]
    fn new(depth: u32) -> Self {
        Ring {
            ring: None,
            depth,
            pinned_mutable_buffers: HashMap::new(),
            pinned_immutable_buffers: HashMap::new(),
            pinned_paths: HashMap::new(),
            pinned_timespecs: HashMap::new(),
            pinned_sockaddr: HashMap::new(),
            pinned_sockopts: HashMap::new(),
            pinned_statx_buffers: HashMap::new(),
        }
    }

    /// Python CM protocol.
    fn __enter__(mut slf: PyRefMut<'_, Self>) -> PyResult<PyRefMut<'_, Self>> {
        let ring = IoUring::new(slf.depth)
            .map_err(|e| PyRuntimeError::new_err(format!("io_uring_setup failed: {e}")))?;
        slf.ring = Some(ring);
        Ok(slf)
    }

    #[pyo3(signature = (_exc_type=None, _exc_val=None, _exc_tb=None))]
    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<'_, PyAny>>,
        _exc_val: Option<&Bound<'_, PyAny>>,
        _exc_tb: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        self.pinned_mutable_buffers.clear();
        self.pinned_immutable_buffers.clear();
        self.pinned_paths.clear();
        self.pinned_sockaddr.clear();
        self.pinned_timespecs.clear();
        self.pinned_sockopts.clear();
        self.pinned_statx_buffers.clear();
        self.ring = None; // Drop triggers internal io_uring cleanup
        Ok(false)
    }

    /// Submit all queued SQEs to the kernel. Returns number submitted.
    fn submit(&mut self) -> PyResult<u32> {
        let n = self
            .uring_mut()?
            .submit()
            .map_err(|e| PyRuntimeError::new_err(format!("io_uring_submit failed: {e}")))?;
        Ok(n as u32)
    }

    /// Non-blocking peek.
    fn peek(&mut self) -> PyResult<Option<CompletionEvent>> {
        let ring = self.uring_mut()?;
        let cq = ring.completion();
        let cqe = cq.into_iter().next();
        match cqe {
            Some(cqe) => Ok(Some(self.cqe_to_event(&cqe))),
            None => Ok(None),
        }
    }

    /// Blocking wait for at least one CQE and return it.
    fn wait(&mut self, py: Python<'_>) -> PyResult<CompletionEvent> {
        let ring = self.uring_mut()?;
        py.detach(|| ring.submit_and_wait(1))
            .map_err(|e| PyRuntimeError::new_err(format!("io_uring_wait failed: {e}")))?;
        let cqe = ring
            .completion()
            .next()
            .ok_or_else(|| PyRuntimeError::new_err("No CQE after wait"))?;
        Ok(self.cqe_to_event(&cqe))
    }

    /// Submit a no-op.
    fn prep_nop(&mut self, user_data: u64) -> PyResult<()> {
        let entry = opcode::Nop::new().build().user_data(user_data);
        self.push_entry(entry)
    }

    /// Submit a timeout (sleep).
    fn prep_timeout(&mut self, user_data: u64, sec: u64, nsec: u32) -> PyResult<()> {
        let timespec = types::Timespec::new().sec(sec).nsec(nsec);
        self.pinned_timespecs.insert(user_data, timespec);
        let ts = self.pinned_timespecs.get(&user_data).unwrap();

        let entry = opcode::Timeout::new(ts).build().user_data(user_data);

        self.push_entry(entry)
    }

    /// Prep a read into `buf`.
    /// The `buf` (a Python `bytearray`) is pinned until the CQE is consumed.
    /// **Do not resize `buf` between prep and consuming the CQE.**
    #[pyo3(signature = (user_data, fd, buf, nbytes, offset))]
    fn prep_read(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyByteArray>,
        nbytes: u32,
        offset: u64,
    ) -> PyResult<()> {
        let ptr = buf.data();
        let len = nbytes.min(buf.len() as u32);

        let entry = opcode::Read::new(types::Fd(fd), ptr.cast(), len)
            .offset(offset)
            .build()
            .user_data(user_data);

        self.pinned_mutable_buffers.insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    // Prepares statx for metadata extraction.
    fn prep_statx(
        &mut self,
        user_data: u64,
        path: &str,
        buf: Bound<'_, StatxBuffer>,
        flags: i32,
        mask: u32,
        dir_fd: RawFd,
    ) -> PyResult<()> {
        let c_path =
            CString::new(path).map_err(|_| PyRuntimeError::new_err("Path contains null byte"))?;
        let path_ptr = c_path.as_ptr();

        let mut guard = buf.borrow_mut();
        let statxbuf_ptr = &mut *guard.inner as *mut libc::statx as *mut io_uring::types::statx;

        let entry = opcode::Statx::new(types::Fd(dir_fd), path_ptr, statxbuf_ptr)
            .flags(flags)
            .mask(mask)
            .build()
            .user_data(user_data);

        drop(guard);

        self.pinned_statx_buffers.insert(
            user_data,
            StatxRequest {
                path: c_path,
                statxbuf: buf.unbind(),
            },
        );
        self.push_entry(entry)
    }

    /// Prep a file write.
    #[pyo3(signature = (user_data, fd, buf, offset))]
    fn prep_write(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyBytes>,
        offset: u64,
    ) -> PyResult<()> {
        let data = buf.as_bytes();
        let ptr = data.as_ptr();
        let len = data.len() as u32;

        let entry = opcode::Write::new(types::Fd(fd), ptr.cast(), len)
            .offset(offset)
            .build()
            .user_data(user_data);

        self.pinned_immutable_buffers
            .insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    /// Prep a file open.
    #[pyo3(signature = (user_data, path, flags, mode, dir_fd))]
    fn prep_openat(
        &mut self,
        user_data: u64,
        path: &str,
        flags: i32,
        mode: u32,
        dir_fd: RawFd,
    ) -> PyResult<()> {
        let c_path =
            CString::new(path).map_err(|_| PyRuntimeError::new_err("Path contains null byte"))?;
        let ptr = c_path.as_ptr();

        let entry = opcode::OpenAt::new(types::Fd(dir_fd), ptr)
            .flags(flags)
            .mode(mode)
            .build()
            .user_data(user_data);

        // Pin the CString so the pointer stays valid until CQE
        self.pinned_paths.insert(user_data, c_path);
        self.push_entry(entry)
    }

    /// Prep a file/socket close.
    fn prep_close(&mut self, user_data: u64, fd: RawFd) -> PyResult<()> {
        let entry = opcode::Close::new(types::Fd(fd))
            .build()
            .user_data(user_data);
        self.push_entry(entry)
    }

    /// Prep a cancellation of another in-flight operation.
    #[pyo3(signature = (user_data, target_user_data, flags = 0))]
    fn prep_cancel(&mut self, user_data: u64, target_user_data: u64, flags: i32) -> PyResult<()> {
        let entry = opcode::AsyncCancel::new(target_user_data)
            .build()
            .user_data(user_data);
        // TODO: use flags once io-uring crate exposes cancel flags
        let _ = flags;
        self.push_entry(entry)
    }

    /// Prep a socket creation.
    #[pyo3(signature = (user_data, domain, sock_type, protocol = 0, flags = 0))]
    fn prep_socket(
        &mut self,
        user_data: u64,
        domain: i32,
        sock_type: i32,
        protocol: i32,
        flags: u32,
    ) -> PyResult<()> {
        let entry = opcode::Socket::new(domain, sock_type, protocol)
            .build()
            .user_data(user_data);
        let _ = flags; // TODO: pass flags if opcode supports it
        self.push_entry(entry)
    }

    /// Prep a recv from a connected socket into `buf`.
    #[pyo3(signature = (user_data, fd, buf, flags = 0))]
    fn prep_socket_recv(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyByteArray>,
        flags: u32,
    ) -> PyResult<()> {
        let ptr = buf.data();
        let len = buf.len() as u32;

        let entry = opcode::Recv::new(types::Fd(fd), ptr.cast(), len)
            .flags(flags as i32)
            .build()
            .user_data(user_data);

        self.pinned_mutable_buffers.insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    /// Prep a send to a connected socket.
    #[pyo3(signature = (user_data, fd, buf, flags = 0))]
    fn prep_socket_send(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyBytes>,
        flags: u32,
    ) -> PyResult<()> {
        let data = buf.as_bytes();
        let ptr = data.as_ptr();
        let len = data.len() as u32;

        let entry = opcode::Send::new(types::Fd(fd), ptr.cast(), len)
            .flags(flags as i32)
            .build()
            .user_data(user_data);

        self.pinned_immutable_buffers
            .insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    /// Preps to bind to a socket.
    fn prep_socket_bind(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        sock_addr: SockAddr,
    ) -> PyResult<()> {
        self.pinned_sockaddr.insert(user_data, sock_addr.inner);

        let stored = self.pinned_sockaddr.get(&user_data).unwrap();
        let (ptr, len) = stored.as_ptr_and_len();

        let entry = opcode::Bind::new(types::Fd(fd), ptr, len)
            .build()
            .user_data(user_data);

        self.push_entry(entry)
    }

    /// Prepares a socket to listen. Marks it as passive.
    fn prep_socket_listen(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        backlog: i32,
    ) -> PyResult<()> {
        let entry = opcode::Listen::new(types::Fd(fd), backlog)
            .build()
            .user_data(user_data);

        self.push_entry(entry)
    }

    /// Prepares a socket to accept an incoming connection.
    /// TODO: Add sockaddr for kernel to fill, for logging who connected.
    fn prep_socket_accept(&mut self, _py: Python<'_>, user_data: u64, fd: RawFd) -> PyResult<()> {
        let entry = opcode::Accept::new(types::Fd(fd), std::ptr::null_mut(), std::ptr::null_mut())
            .build()
            .user_data(user_data);

        self.push_entry(entry)
    }

    /// Connects to a socket from a client.
    fn prep_socket_connect(
        &mut self,
        _py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        sock_addr: SockAddr,
    ) -> PyResult<()> {
        self.pinned_sockaddr.insert(user_data, sock_addr.inner);

        let stored = self.pinned_sockaddr.get(&user_data).unwrap();
        let (ptr, len) = stored.as_ptr_and_len();

        let entry = opcode::Connect::new(types::Fd(fd), ptr, len)
            .build()
            .user_data(user_data);

        self.push_entry(entry)
    }

    /// Set socket options.
    fn prep_socket_setopt(&mut self, user_data: u64, fd: RawFd) -> PyResult<()> {
        // TODO: Hardcoded for now.
        let optval = Box::new(1i32); // SO_REUSEADDR value
        self.pinned_sockopts.insert(user_data, optval);
        let pinned = self.pinned_sockopts.get(&user_data).unwrap();

        let entry = opcode::SetSockOpt::new(
            types::Fd(fd),
            libc::SOL_SOCKET as u32,
            libc::SO_REUSEADDR as u32,
            pinned.as_ref() as *const i32 as *const libc::c_void,
            std::mem::size_of::<i32>() as u32,
        )
        .build()
        .user_data(user_data);

        self.push_entry(entry)
    }
}

//TODO: Move to another module.
#[derive(Clone)]
enum SockAddrInner {
    V4(libc::sockaddr_in),
    V6(libc::sockaddr_in6),
}

impl SockAddrInner {
    /// Returns address as pointer as well as its length.
    fn as_ptr_and_len(&self) -> (*const libc::sockaddr, u32) {
        match &self {
            SockAddrInner::V4(addr) => (
                addr as *const libc::sockaddr_in as *const libc::sockaddr,
                std::mem::size_of::<libc::sockaddr_in>() as u32,
            ),
            SockAddrInner::V6(addr) => (
                addr as *const libc::sockaddr_in6 as *const libc::sockaddr,
                std::mem::size_of::<libc::sockaddr_in6>() as u32,
            ),
        }
    }
}

#[pyclass]
#[derive(Clone)]
struct SockAddr {
    inner: SockAddrInner,
}

#[pymethods]
impl SockAddr {
    #[staticmethod]
    fn v4(ip: &str, port: u16) -> PyResult<Self> {
        let addr_parsed: Ipv4Addr = ip
            .parse()
            .map_err(|e| PyValueError::new_err(format!("Invalid IPv4 address: {e}")))?;

        let mut addr: libc::sockaddr_in = unsafe { std::mem::zeroed() };
        addr.sin_family = libc::AF_INET as u16;
        addr.sin_addr.s_addr = u32::from_ne_bytes(addr_parsed.octets());
        addr.sin_port = port.to_be();
        Ok(SockAddr {
            inner: SockAddrInner::V4(addr),
        })
    }

    #[staticmethod]
    fn v6(ip: &str, port: u16) -> PyResult<Self> {
        let addr_parsed: Ipv6Addr = ip
            .parse()
            .map_err(|e| PyValueError::new_err(format!("Invalid IPv6 address: {e}")))?;

        let mut addr: libc::sockaddr_in6 = unsafe { std::mem::zeroed() };
        addr.sin6_family = libc::AF_INET6 as u16;
        addr.sin6_addr.s6_addr = addr_parsed.octets();
        addr.sin6_port = port.to_be();
        Ok(SockAddr {
            inner: SockAddrInner::V6(addr),
        })
    }
}

#[pyclass]
#[derive(Clone, Debug)]
struct StatxBuffer {
    inner: Box<libc::statx>,
}

#[pymethods]
impl StatxBuffer {
    #[new]
    fn new() -> Self {
        StatxBuffer {
            inner: Box::new(unsafe { std::mem::zeroed() }),
        }
    }

    #[getter]
    fn size(&self) -> u64 {
        self.inner.stx_size
    }

    #[getter]
    fn mtime_sec(&self) -> i64 {
        self.inner.stx_mtime.tv_sec
    }

    #[getter]
    fn ino(&self) -> u64 {
        self.inner.stx_ino
    }

    #[getter]
    fn mode(&self) -> u32 {
        self.inner.stx_mode as u32
    }
}

fn register_constants(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // File open flags
    m.add("O_RDONLY", libc::O_RDONLY)?;
    m.add("O_WRONLY", libc::O_WRONLY)?;
    m.add("O_RDWR", libc::O_RDWR)?;
    m.add("O_CREAT", libc::O_CREAT)?;
    m.add("O_TRUNC", libc::O_TRUNC)?;
    m.add("O_APPEND", libc::O_APPEND)?;
    m.add("O_NONBLOCK", libc::O_NONBLOCK)?;
    m.add("O_CLOEXEC", libc::O_CLOEXEC)?;

    // File mode bits (permissions)
    m.add("S_IRUSR", libc::S_IRUSR)?;
    m.add("S_IWUSR", libc::S_IWUSR)?;
    m.add("S_IXUSR", libc::S_IXUSR)?;
    m.add("S_IRGRP", libc::S_IRGRP)?;
    m.add("S_IWGRP", libc::S_IWGRP)?;
    m.add("S_IXGRP", libc::S_IXGRP)?;
    m.add("S_IROTH", libc::S_IROTH)?;
    m.add("S_IWOTH", libc::S_IWOTH)?;
    m.add("S_IXOTH", libc::S_IXOTH)?;

    // File type bits (from st_mode / stx_mode)
    m.add("S_IFREG", libc::S_IFREG)?;
    m.add("S_IFDIR", libc::S_IFDIR)?;
    m.add("S_IFLNK", libc::S_IFLNK)?;
    m.add("S_IFSOCK", libc::S_IFSOCK)?;
    m.add("S_IFIFO", libc::S_IFIFO)?;
    m.add("S_IFMT", libc::S_IFMT)?;

    // AT flags (path resolution)
    m.add("AT_FDCWD", libc::AT_FDCWD)?;
    m.add("AT_EMPTY_PATH", libc::AT_EMPTY_PATH)?;
    m.add("AT_SYMLINK_NOFOLLOW", libc::AT_SYMLINK_NOFOLLOW)?;

    // Statx mask (which fields to populate)
    m.add("STATX_TYPE", libc::STATX_TYPE)?;
    m.add("STATX_MODE", libc::STATX_MODE)?;
    m.add("STATX_INO", libc::STATX_INO)?;
    m.add("STATX_SIZE", libc::STATX_SIZE)?;
    m.add("STATX_MTIME", libc::STATX_MTIME)?;
    m.add("STATX_ATIME", libc::STATX_ATIME)?;
    m.add("STATX_CTIME", libc::STATX_CTIME)?;
    m.add("STATX_ALL", libc::STATX_ALL)?;

    // Socket: address families
    m.add("AF_INET", libc::AF_INET)?;
    m.add("AF_INET6", libc::AF_INET6)?;
    m.add("AF_UNIX", libc::AF_UNIX)?;

    // Socket: types
    m.add("SOCK_STREAM", libc::SOCK_STREAM)?;
    m.add("SOCK_DGRAM", libc::SOCK_DGRAM)?;
    m.add("SOCK_NONBLOCK", libc::SOCK_NONBLOCK)?;
    m.add("SOCK_CLOEXEC", libc::SOCK_CLOEXEC)?;

    // Socket: protocol levels and options
    m.add("SOL_SOCKET", libc::SOL_SOCKET)?;
    m.add("SO_REUSEADDR", libc::SO_REUSEADDR)?;
    m.add("SO_REUSEPORT", libc::SO_REUSEPORT)?;
    m.add("SO_KEEPALIVE", libc::SO_KEEPALIVE)?;
    m.add("IPPROTO_TCP", libc::IPPROTO_TCP)?;
    m.add("TCP_NODELAY", libc::TCP_NODELAY)?;

    // Socket: send/recv flags
    m.add("MSG_NOSIGNAL", libc::MSG_NOSIGNAL)?;
    m.add("MSG_DONTWAIT", libc::MSG_DONTWAIT)?;

    // Signals
    m.add("SIGINT", libc::SIGINT)?;
    m.add("SIGTERM", libc::SIGTERM)?;
    m.add("SIGHUP", libc::SIGHUP)?;

    // Signalfd flags
    m.add("SFD_NONBLOCK", libc::SFD_NONBLOCK)?;
    m.add("SFD_CLOEXEC", libc::SFD_CLOEXEC)?;

    Ok(())
}

#[pymodule]
fn _rusty_ring(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Ring>()?;
    m.add_class::<CompletionEvent>()?;
    m.add_class::<SockAddr>()?;
    m.add_class::<StatxBuffer>()?;

    register_constants(m)?;
    Ok(())
}
