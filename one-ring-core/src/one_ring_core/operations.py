from dataclasses import dataclass


@dataclass(frozen=True)
class IOOperation:
    """Base class for all IO operations"""

    def prep(self, sqe: SubmissionQueueEntry) -> None:
        """Prepares a submission queue entry for the SQ"""
        raise NotImplementedError("Operations should implement prepare method")

    @classmethod
    def extract(cls, cqe) -> None:
        """Extract fields from a completion queue event and wrap in correct type"""
        raise NotImplementedError("Operations should implement prepare method")

@dataclass(frozen=True)
class FileIO(IOOperation):
    """Base class for all file IO operations"""

@dataclass(frozen=True)
class NetworkIO(IOOperation):
    """Base class for all networking IO operations"""

@dataclass(frozen=True)
class TimerIO(IOOperation):
    """Base class for all timer IO operations"""

@dataclass(frozen=True)
class ControlIO(IOOperation):
    """Base class for all control IO operations"""

@dataclass(frozen=True)
class FileOpen(FileIO):
    path: bytes
    mode: str

    def prep(self, sqe: SubmissionQueueEntry) -> None:
        """Prepares a submission queue entry for the SQ"""
        raise NotImplementedError("Operations should implement prepare method")

    @classmethod
    def extract(cls, cqe) -> None:
        """Extract fields from a completion queue event and wrap in correct type"""
        raise NotImplementedError("Operations should implement prepare method")

@dataclass(frozen=True)
class FileRead(FileIO):
    fd: int

    """None will read the whole file"""
    size: int | None = None

    def prep(self, sqe: SubmissionQueueEntry) -> None:
        """Prepares a submission queue entry for the SQ"""
        raise NotImplementedError("Operations should implement prepare method")

    @classmethod
    def extract(cls, cqe) -> None:
        """Extract fields from a completion queue event and wrap in correct type"""
        raise NotImplementedError("Operations should implement prepare method")

@dataclass(frozen=True)
class FileWrite(FileIO):
    fd: int
    data: bytes

    def prep(self, sqe: SubmissionQueueEntry) -> None:
        """Prepares a submission queue entry for the SQ"""
        raise NotImplementedError("Operations should implement prepare method")

    @classmethod
    def extract(cls, cqe) -> None:
        """Extract fields from a completion queue event and wrap in correct type"""
        raise NotImplementedError("Operations should implement prepare method")

@dataclass(frozen=True)
class FileClose(FileIO):
    fd: int

    def prep(self, sqe: SubmissionQueueEntry) -> None:
        """Prepares a submission queue entry for the SQ"""
        raise NotImplementedError("Operations should implement prepare method")

    @classmethod
    def extract(cls, cqe) -> None:
        """Extract fields from a completion queue event and wrap in correct type"""
        raise NotImplementedError("Operations should implement prepare method")
