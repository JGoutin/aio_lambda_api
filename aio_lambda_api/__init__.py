"""Async AWS Lambda handler."""
from aio_lambda_api.core import Handler
from aio_lambda_api.exceptions import HTTPException
from aio_lambda_api.json import loads, dumps
from aio_lambda_api.logging import get_logger
from aio_lambda_api.requests import Request
from aio_lambda_api.responses import JSONResponse, Response

__all__ = (
    "Handler",
    "HTTPException",
    "loads",
    "dumps",
    "settings",
    "get_logger",
    "JSONResponse",
    "Response",
    "Request",
)

try:
    import uvloop as _uvloop  # noqa
except ImportError:  # pragma: no cover
    pass
else:
    _uvloop.install()
