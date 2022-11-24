"""Logging."""
from contextlib import contextmanager
from contextvars import ContextVar as _ContextVar
from typing import Any as _Any, Dict as _Dict, Iterator as _Iterator
from time import perf_counter as _perf_counter
from aio_lambda_api.json import dumps as _dumps

context_log: _ContextVar[_Dict[str, _Any]] = _ContextVar("context_log")

_DEFAULT_LOG: _Dict[str, _Any] = dict(level="info")


def get_logger() -> _Dict[str, _Any]:
    """Get the current request logger.

    Returns:
        Log dict.
    """
    return context_log.get()


@contextmanager
def logger(server: str) -> _Iterator[_Dict[str, _Any]]:
    """Logger context manager.

    Args:
        server: Serveur ID.

    Returns:
        Logger.
    """
    start = _perf_counter()

    # Keep the same value for server if lambda reuse the same cached function
    _DEFAULT_LOG.setdefault("server", server)

    log = _DEFAULT_LOG.copy()
    context_log.set(log)

    try:
        yield log
    except Exception as exc:
        from traceback import format_exception as _format_exception

        log["level"] = "critical"
        log["status_code"] = 500
        log["error_detail"] = "".join(
            _format_exception(type(exc), exc, exc.__traceback__)
        )
        raise
    finally:
        log["execution_time_ms"] = round((_perf_counter() - start) * 1e3, 1)
        print(_dumps(log))
