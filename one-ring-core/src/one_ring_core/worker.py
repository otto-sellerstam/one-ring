
class IOWorker:
    def __init__(self):
        self._ring = io_uring()
        io_uring_queue_init(32, self._ring, 0)  # Not sure about parameters.
        self._cqe = io_uring_cqe()

        # Maps user_data (internal) to respective operation.
        self._active_submissions: dict[UserData, IOOperation] = {}

        # Buffers for reading data.
        self._iovecs: dict[UserData, MutableIOVec] = {}

    def register(self, operation: IOOperation) -> UserData:
        """Registers op_type in the SQ"""
        match operation:
            case FileOpen(path, mode):
                flags = file_open_mode_to_flags(mode)
                user_data = self._register_file_open(path, flags)
            case FileRead(fd, size):
                user_data = self._register_file_read(fd, size)
            case FileWrite(fd, data):
                user_data = self._register_file_write(fd, data)
            case FileClose(fd):
                user_data = self._register_file_close(fd)
            case _:
                raise TypeError(f"Unsupported operation: {operation}")

        self._add_submission(user_data, operation)
        return user_data

    def _get_user_data(self) -> UserData:
        """Gets the smallest positive number which is unused
        TODO: Optimize.
        """
        user_data = 1
        while user_data <= len(self._active_submissions):
            if user_data not in self._active_submissions:
                break

            user_data += 1

        return user_data

    def _add_submission(self, user_data: UserData, operation: IOOperation) -> None:
        self._active_submissions[user_data] = operation

    def _pop_submission(self, user_data: UserData) -> IOOperation:
        """
        Pops and returns a submission from the internal tracking of active submissions.

        Args:
            user_data: the submission to pop.

        Returns:
            The popped submission.
        """
        return self._active_submissions.pop(user_data)

    def _register_file_open(
        self,
        path: bytes,
        flags: int,
        mode: int = 0o660,
        dir_fd: int = AT_FDCWD,
    ) -> UserData:
        """Get a SQE from the SQ and prepare it to open a file.

        Args:
            path: the path of the file to open in bytes.
            flags: permissions for the operation.
            user_data: internal tracking of submissions and completes.
            mode: not sure.
            dir_fd: not sure.
        """
        sqe = self._get_sqe()
        sqe.prep_openat(path, flags, mode, dir_fd)
        return sqe.user_data

    def _register_file_read(
        self,
        fd: int,
        size: int | None,
        offset: int = 0,
    ) -> UserData:
        """Get a SQE from the SQ and prepare it to read a file."""
        _size = size
        if _size is None:
            _size = os.fstat(fd).st_size
        iov = MutableIOVec(bytearray(_size))

        sqe: SubmissionQueueEntry = self._get_sqe()
        sqe.prep_read(fd, iov, offset)
        self._iovecs[sqe.user_data] = iov
        return sqe.user_data

    def _register_file_write(
        self,
        fd: int,
        data: bytes,
        offset: int = 0,
    ) -> UserData:
        """Get an SQE from the SQ and prepare it to write to a file."""
        vector_buffer = IOVec(data)
        sqe = self._get_sqe()
        sqe.prep_write(fd, vector_buffer, offset)
        return sqe.user_data

    def _register_file_close(
        self,
        fd: int,
    ) -> UserData:
        sqe = self._get_sqe()
        sqe.prep_close(fd)
        return sqe.user_data

    def submit(self) -> None:
        """Submits the SQ to the kernel"""
        # This should check that all new registrations where actually submitted
        io_uring_submit(self._ring)

    def wait(self) -> IOCompletion:
        """Blocking check if a completion event is available

        Returns:
            IOCompletion
        """

        io_uring_wait_cqe(self._ring, self._cqe)
        return self._extract_cqe()

    def peek(self) -> IOCompletion | None:
        """Nonblocking check if a completion event is available

        Returns:
            IOCompletion if available, otherwise None.
        """
        if io_uring_peek_cqe(self._ring, self._cqe) == 0:
            return self._extract_cqe()

        return None

    def _extract_cqe(self) -> IOCompletion:
        """
        Fetches data from completion event and transforms to relevant type.
        """
        user_data = self._cqe.user_data
        # Now we need to handle the CQE based on the operation type of the submission.
        operation = self._pop_submission(user_data)
        try:
            match operation:
                case FileOpen():
                    result =  FileOpenResult(
                        fd=self._cqe.res,
                    )
                case FileRead():
                    vector_buffer = self._iovecs.pop(user_data)
                    result = FileReadResult(
                        content=vector_buffer.iov_base.decode(),
                        size=self._cqe.res,
                    )
                case FileWrite():
                    result = FileWriteResult(
                        size=self._cqe.res,
                    )
                case FileClose():
                    result = FileCloseResult()
                case _:
                    raise TypeError(f"Unsupported operation: {operation}")
        finally:
            io_uring_cqe_seen(self._ring, self._cqe)

        return IOCompletion(
            user_data=user_data,
            result=result,
        )

    def _get_sqe(self) -> SubmissionQueueEntry :
        sqe = io_uring_get_sqe(self._ring)
        user_data = self._get_user_data()
        return SubmissionQueueEntry(sqe, user_data)
