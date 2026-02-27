"""This will be a docstring."""

from __future__ import annotations

import os
from contextlib import ExitStack
from typing import TYPE_CHECKING, Self

from one_ring_core.log import get_logger
from one_ring_core.results import IOCompletion, IOResult
from rusty_ring import CompletionEvent, Ring

if TYPE_CHECKING:
    from types import TracebackType

    from one_ring_core.operations import IOOperation
    from one_ring_core.typedefs import WorkerOperationID


logger = get_logger(__name__)


class IOWorker:
    """Docstring."""

    def __init__(self) -> None:
        self._active_submissions: dict[WorkerOperationID, IOOperation] = {}

    def register(
        self,
        operation: IOOperation,
        identifier: WorkerOperationID,
    ) -> WorkerOperationID:
        """Registers operation in the SQ."""
        operation.prep(identifier, self._ring)

        self._add_submission(identifier, operation)
        return identifier

    def _add_submission(
        self, identifier: WorkerOperationID, operation: IOOperation
    ) -> None:
        self._active_submissions[identifier] = operation

    def _pop_submission(self, identifier: WorkerOperationID) -> IOOperation:
        """Pops a submission from the internal tracking of active submissions.

        Args:
            user_data: the submission to pop.
            identifier: the identifier provided externally for the IO operation.

        Returns:
            The popped submission.
        """
        return self._active_submissions.pop(identifier)

    def submit(self) -> None:
        """Submits the SQ to the kernel."""
        # This should check that all new registrations where actually submitted
        self._ring.submit()

    def wait(self) -> IOCompletion[IOResult]:
        """Blocking check if a completion event is available.

        Returns:
            IOCompletion
        """
        completion_event = self._ring.wait()
        return self._transform_completion_event(completion_event)

    def peek(self) -> IOCompletion[IOResult] | None:
        """Nonblocking check if a completion event is available.

        Returns:
            IOCompletion if available, otherwise None.
        """
        if (completion_event := self._ring.peek()) is not None:
            return self._transform_completion_event(completion_event)

        return completion_event

    def __enter__(self) -> Self:
        """Docstring."""
        self._stack = ExitStack()
        self._stack.__enter__()
        self._ring = self._stack.enter_context(Ring(depth=32))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Docstring."""
        self._stack.__exit__(exc_type, exc_val, exc_tb)

    def _transform_completion_event(
        self,
        completion_event: CompletionEvent,
    ) -> IOCompletion[IOResult]:
        """Fetches data from completion event and transforms to relevant type."""
        user_data = completion_event.user_data
        # Now we need to handle the CQE based on the operation type of the submission.
        operation: IOOperation[IOResult] = self._pop_submission(user_data)

        # Check for failures.
        cqe_result = completion_event.res
        if not operation.is_error(completion_event):
            result = operation.extract(completion_event)
        else:
            error_code = -cqe_result
            error_message = os.strerror(error_code)
            result = OSError(-cqe_result, error_message)

        return IOCompletion(
            user_data=user_data,
            result=result,
        )
