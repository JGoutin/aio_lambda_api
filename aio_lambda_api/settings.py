"""Settings."""
from os import getenv as _getenv

# Default lambda function timeout (seconds)
FUNCTION_TIMEOUT = int(_getenv("FUNCTION_TIMEOUT", 30))

# Default connection timeout (seconds)
CONNECTION_TIMEOUT = int(_getenv("CONNECTION_TIMEOUT", 5))

# Default read timeout (seconds)
READ_TIMEOUT = int(_getenv("READ_TIMEOUT", 15))
