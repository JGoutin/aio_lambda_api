"""Exceptions."""
from typing import Any as _Any, Optional as _Optional, Dict as _Dict
from aio_lambda_api.status import get_status_message as _get_status_message

__all__ = ("HTTPException", "ValidationError")


try:
    from pydantic import ValidationError
except ImportError:

    class ValidationError(Exception):  # type: ignore
        """Validation Error."""

        __slots__ = ["_errors"]

        def __init__(self, errors: _Any) -> None:
            self._errors = errors

        def errors(self) -> _Any:
            """Returns errors.

            Returns:
                Errors.
            """
            return self._errors


class HTTPException(Exception):
    """Exception returned as result to client with an HTTP return code."""

    __slots__ = ["status_code", "_error_detail", "_detail", "headers"]

    def __init__(
        self,
        status_code: int,
        detail: _Any = None,
        headers: _Optional[_Dict[str, _Any]] = None,
        *,
        error_detail: _Optional[_Any] = None,
    ) -> None:
        self.status_code = int(status_code)
        self._detail = detail
        self.headers = headers
        self._error_detail = error_detail
        Exception.__init__(self)

    @property
    def detail(self) -> str:
        """Message.

        Returns:
            Message.
        """
        return self._detail or _get_status_message(self.status_code)

    @property
    def error_detail(self) -> _Optional[str]:
        """Internal error details.

        Shown in logs, but not returned to caller.

        Returns:
            Message.
        """
        if self._error_detail:
            return str(self._error_detail)
        elif self._detail:
            return str(self._detail)
        return None
