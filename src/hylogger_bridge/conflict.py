# Purpose: the one error for a request that the book's current state refuses.


class BookConflict(ValueError):
    """A stale request, locked page or reused request ID prevents a mutation."""

    def __init__(self, message: str, code: str = "stale_revision") -> None:
        super().__init__(message)
        self.code = code
