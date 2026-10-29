"""Errors that map to the exit codes in SPEC section 3."""


class InputError(Exception):
    """Invalid input file (exit code 1)."""


class BackendError(Exception):
    """Model backend unavailable or unusable output (exit code 3)."""
