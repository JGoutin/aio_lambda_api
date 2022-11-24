"""AWS related."""
from os import getenv as _getenv
from botocore.client import Config as _Config
from botocore import serialize as _serialize, parsers as _parsers
from aio_lambda_api.settings import (
    CONNECTION_TIMEOUT as _CONNECTION_TIMEOUT,
    READ_TIMEOUT as _READ_TIMEOUT,
)
import aio_lambda_api.json as _json


#: Default Boto client/resource configuration
BOTO_CLIENT_CONFIG = _Config(
    connect_timeout=_CONNECTION_TIMEOUT,
    read_timeout=_READ_TIMEOUT,
    parameter_validation=bool(_getenv("BOTO_PARAMETER_VALIDATION", "")),
    max_pool_connections=int(_getenv("BOTO_MAX_POOL_CONNECTIONS", 100)),
)

# Speed up Botocore JSON handling
_serialize.json = _json  # type: ignore
_parsers.json = _json  # type: ignore
