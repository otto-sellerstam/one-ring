use io_uring::{opcode, types, IoUring};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyByteArray;
use std::collections::HashMap;
use std::ffi::CString;
use std::os::unix::io::RawFd;

// ---------------------------------------------------------------------------
// CompletionEvent
// ---------------------------------------------------------------------------

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

/// Owns an io_uring instance and exposes prep/submit/complete operations.
///
/// Usage from Python:
///
///     with Ring(depth=32) as ring:
///         ring.prep_nop(user_data=1)
///         ring.submit()
///         cqe = ring.wait()
///
#[pyclass]
struct Ring {
    ring: Option<IoUring>,
    depth: u32,

    /// Buffers that are currently owned by the kernel (between submit and CQE).
    /// Keyed by user_data so they can be released when the CQE arrives.
    ///
    /// The kernel holds raw pointers into these buffers. They must be keet
    /// alive and un-resized until the corresponding CQE is consumed.
    pinned_buffers: HashMap<u64, Py<PyByteArray>>,

    /// CStrings for paths passed to openat; same lifetime concern as buffers.
    pinned_paths: HashMap<u64, CString>,
}

impl Ring {
    //fn uring(&self) -> PyResult<&IoUring> {
    //    self.ring
    //        .as_ref()
    //        .ok_or_else(|| PyRuntimeError::new_err("Ring not initialised (use as context manager)"))
    //}

    fn uring_mut(&mut self) -> PyResult<&mut IoUring> {
        self.ring
            .as_mut()
            .ok_or_else(|| PyRuntimeError::new_err("Ring not initialised (use as context manager)"))
    }

    /// Push an entry onto the SQ.  Panics if SQ is full: caller should size
    /// the ring appropriately or check before calling.
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
        self.pinned_buffers.remove(&user_data);
        self.pinned_paths.remove(&user_data);
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
            pinned_buffers: HashMap::new(),
            pinned_paths: HashMap::new(),
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
        self.pinned_buffers.clear();
        self.pinned_paths.clear();
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
    fn wait(&mut self) -> PyResult<CompletionEvent> {
        let ring = self.uring_mut()?;
        ring.submit_and_wait(1)
            .map_err(|e| PyRuntimeError::new_err(format!("io_uring_wait failed: {e}")))?;
        let cqe = ring
            .completion()
            .next()
            .ok_or_else(|| PyRuntimeError::new_err("No CQE after wait"))?;
        Ok(self.cqe_to_event(&cqe))
    }

    // Buffer-carrying operations pin the buffer in `pinned_buffers`.

    /// Submit a no-op.
    fn prep_nop(&mut self, user_data: u64) -> PyResult<()> {
        let entry = opcode::Nop::new().build().user_data(user_data);
        self.push_entry(entry)
    }

    /// Prep a read into `buf`.
    /// The `buf` (a Python `bytearray`) is pinned until the CQE is consumed.
    /// **Do not resize `buf` between prep and consuming the CQE.**
    #[pyo3(signature = (user_data, fd, buf, nbytes, offset))]
    fn prep_read(
        &mut self,
        py: Python<'_>,
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

        self.pinned_buffers.insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    /// Prep a file write.
    #[pyo3(signature = (user_data, fd, buf, nbytes, offset))]
    fn prep_write(
        &mut self,
        py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyByteArray>,
        nbytes: u32,
        offset: u64,
    ) -> PyResult<()> {
        let ptr = buf.data();
        let len = nbytes.min(buf.len() as u32);

        let entry = opcode::Write::new(types::Fd(fd), ptr.cast(), len)
            .offset(offset)
            .build()
            .user_data(user_data);

        self.pinned_buffers.insert(user_data, buf.unbind());
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
        let c_path = CString::new(path)
            .map_err(|_| PyRuntimeError::new_err("Path contains null byte"))?;
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
    fn prep_cancel(
        &mut self,
        user_data: u64,
        target_user_data: u64,
        flags: i32,
    ) -> PyResult<()> {
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
    fn prep_recv(
        &mut self,
        py: Python<'_>,
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

        self.pinned_buffers.insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    /// Prep a send to a connected socket.
    #[pyo3(signature = (user_data, fd, buf, flags = 0))]
    fn prep_send(
        &mut self,
        py: Python<'_>,
        user_data: u64,
        fd: RawFd,
        buf: Bound<'_, PyByteArray>,
        flags: u32,
    ) -> PyResult<()> {
        let ptr = buf.data();
        let len = buf.len() as u32;

        let entry = opcode::Send::new(types::Fd(fd), ptr.cast(), len)
            .flags(flags as i32)
            .build()
            .user_data(user_data);

        self.pinned_buffers.insert(user_data, buf.unbind());
        self.push_entry(entry)
    }

    // TODO: prep_timeout, prep_bind, prep_listen, prep_accept, prep_connect,
    // prep_setsockopt.
}

// ---------------------------------------------------------------------------
// Module
// ---------------------------------------------------------------------------

#[pymodule]
fn _rusty_ring(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Ring>()?;
    m.add_class::<CompletionEvent>()?;
    Ok(())
}
