"""In-process download job exceptions."""


class JobCancelled(RuntimeError):
    """Raised when the user cancels an in-process download."""
