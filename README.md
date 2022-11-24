![Tests](https://github.com/JGoutin/aio_lambda_api/workflows/tests/badge.svg)
[![codecov](https://codecov.io/gh/JGoutin/aio_lambda_api/branch/main/graph/badge.svg?token=52KXxxDFhx)](https://codecov.io/gh/JGoutin/aio_lambda_api)
[![PyPI](https://img.shields.io/pypi/v/aio_lambda_api.svg)](https://pypi.org/project/aio_lambda_api)

A lightweight AsyncIO HTTP API for AWS lambda.

Features:
* Asyncio in AWS lambda.
* FastAPI inspired routing, parameters and exception handling.
* Compatible with AWS API gateway request/responses format.
* Detailed JSON formatted access log (Works well with AWS Cloudwatch Insight).
* X-Request-ID header support (Including in logs).
* Configurable request timeout.
* Optional input validation using Pydantic.
* Optional JSON serialization/deserialization speedup with Orjson.
* optional AsyncIO loop speed up with Uvloop.

Not supported yet:
* Routes with variables (Like `"/items/{item_id}"`).
* Query strings.
* * Pydantic models as response or request body.
* AWS SSM parameter store helper.

## Usage

### Usage with AWS lambda

Lambda function code example (`app.py`):
```python
from aio_lambda_api import Handler

handler = Handler()

@handler.get("/")
def read_root():
    return {"Hello": "World"}
```
AWS lambda function handler must be configured to `app.handler`.

### Routing

The `aio_lambda_api.Handler` class provides decorators to configure routes for each 
HTTP method:
* `Handler.get()`: GET.
* `Handler.head()`: HEAD.
* `Handler.post()`: POST.
* `Handler.put()`: PUT.
* `Handler.patch()`: PATCH.
* `Handler.delete()`: DELETE.
* `Handler.options()`: OPTIONS.

For all decorators, the first arguments is the HTTP path and is required.

The decorated function is executed when the defined HTTP path and method matches.

By default, the body of the request is parsed as JSON and injected in the function as 
arguments.
If Pydantic is installed, parameters are validated against arguments types annotations.

The decorated function must return a JSON serializable object or `None`. If the function
returns `None`, the returned status code is automatically set to `204`.

### Exception handling

It is possible to trigger a response using the `aio_lambda_api.HTTPException` as follow:

```python
from aio_lambda_api import Handler, HTTPException

handler = Handler()

items = {"foo": "The Foo Wrestlers"}

@handler.get("/item")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```

If an exception is risen in routes functions, the behavior is the following:
* `aio_lambda_api.HTTPException`: Converted to HTTP response with the 
  specified body and returns code.
* `pydantic.ValidationError`: Converted to 422 HTTP error response with Pydantic error 
  details as body.
* Other exceptions: Reraised. Callers using the Lambda API will
  be able to analyse the error like any other Python lambda error 
  (With `errorType`, `errorMessage` and `stackTrace`)
  Callers using an HTTP endpoint/API gateway will receive a simple 500 error with no
  details.

### Customizing responses

#### Return code

It is possible to select the return code (when no exception occurs) using the
`status_code` argument. If not specified `200` is used.

```python
from aio_lambda_api import Handler

handler = Handler()

@handler.get("/", status_code=201)
def read_root():
    return {"Hello": "World"}
```

#### Headers

It is possible to configure headers by using the `Response` object from arguments:

```python
from aio_lambda_api import Handler, Response

handler = Handler()

@handler.get("/")
async def read_item(response: Response):
    response.headers["Cache-Control"] = "no-cache"

    return {"Hello": "World"}
```

#### Custom response

It is possible to fully configure the response by returning the `Response` object.

```python
from aio_lambda_api import Handler, Response

handler = Handler()

@handler.get("/")
async def read_item():
    return Response(
      status_code=202,
      media_type="application/octet-stream",
      content=b"helloworld"
    )
```

The default `Response` class accept `str` or `bytes` as content.

The `JSONResponse` object is also available, it is the default response object when not 
explicitly set.

It is possible to create a subclass of `Response` class to have a custom behavior. The
`Response.render` method is responsible for the serialization of the response.

Note: If a response class returns a `bytes` content after `Response.render`, this
content will be base64 encoded automatically in the API Gateway compatible response
returned.

### Accessing Request data

It is possible to access request data by using the `Request` object from arguments:

```python
from aio_lambda_api import Handler, Request

handler = Handler()

@handler.get("/")
async def read_item(request: Request):
    user_agent = request.headers["user-agent"]
    return {"Hello": user_agent}
```

Note: All headers keys are lowercase in the `Request` object.

### Logging

An access log is automatically generated. This access log is in JSON format (`dict` in 
the code). With AWS lambda, the logs will appear with other lambda logs in Cloudwatch 
logs. The JSON format make them very easy to query in Cloudwatch Insight.

All request and all exceptions from routes functions are logged in the access log 
(Including reraised 500 errors.)

When raising `aio_lambda_api.HTTPException`, it is possible to show extra information
on the logs using the `error_detail` arguments (This will be shown in logs but will not
be visible by the client in the response).

The logger dict can be accessed from any routes functions using the
`aio_lambda_api.get_logger` function. This can be used to add custom logs entries. All
log entries must be JSON serializable.

Defaults log fields:
* `error_detail`: `error_detail` argument value of `aio_lambda_api.HTTPException`.
* `execution_time_ms`: Execution time in ms of the route function.
* `level`: Logging level (`info`, `warning`, `error`, `critical`).
* `method`: HTTP method of the request.
* `path`: HTTP path of the request.
* `request_id`: `X-Request-Id` header is present else AWS lambda `requestId`.
* `server`: Server running the lambda. This is the ID of the first lambda function call,
  so this value will not change if lambda reuse the same context in another function 
  call.
* `status_code`: HTTP status code of the response.

### Async initialization

In AWS lambda the asyncio context is limited to the routes functions.

But, the `aio_lambda_api.Handler` class provides methods to run async function outside 
routes functions:
* `Handler.run_async`: Runs an async function and returns the result.
* `Handler.enter_async_context`: Initialize an async contextmanager and returns the
  initialized object. The Context manager is also attached to the 
 `aio_lambda_api.Handler` exit stack (And will be exited with the handler; note that 
  there is no guarantee that this is executed with AWS lambda).

```python
from aio_lambda_api import Handler
from database import Database

handler = Handler()

# Initialize a database connection outside routes functions
# AWS lambda will keep this value cached between runs

async def init_database():
  db = Database()
  await db.connect()
  return db

DB = handler.run_async(init_database())

# Variable can then be used normally from routes functions

@handler.get("/user")
def get_fron_db():
  return await DB.select("*")

```

### Configuration 

#### Settings

These settings are passed to the handle with environment variables.

* `FUNCTION_TIMEOUT`: The route function call timeout in seconds. 
  Available as `aio_lambda_api.settings.FUNCTION_TIMEOUT`. Default to 30s.
* `CONNECTION_TIMEOUT`: Global connection timeout in seconds.
  Available as `aio_lambda_api.settings.CONNECTION_TIMEOUT`.
  Also used in `aio_lambda_api.aws.BOTO_CLIENT_CONFIG`. Default to 5s.
* `READ_TIMEOUT`: Global read timeout in seconds.
  Available as `aio_lambda_api.settings.READ_TIMEOUT`.
  Also used in `aio_lambda_api.aws.BOTO_CLIENT_CONFIG`. Default to 15s.
* `BOTO_PARAMETER_VALIDATION`: If set enable `boto3` input validation in 
  `aio_lambda_api.aws.BOTO_CLIENT_CONFIG`. Disabled by default to improve 
  performance.
* `BOTO_MAX_POOL_CONNECTIONS`: `boto3` `max_pool_connections` in 
  `aio_lambda_api.aws.BOTO_CLIENT_CONFIG`. Default to 100.

#### AWS utilities

##### Botocore default config.

A `botocore.client.Config` is provided as 
`aio_lambda_api.aws.BOTO_CLIENT_CONFIG` and can be used with `aioboto3` 
clients and resources.

```python
import aioboto3
from aio_lambda_api.aws import BOTO_CLIENT_CONFIG

session = aioboto3.Session()
async with session.resource("s3", config=BOTO_CLIENT_CONFIG) as s3:
    pass
```

##### aiobotocore & aioboto3 performance speed up

botocore/aiobotocore is configured to use orjson is available to speed up JSON 
serialization/deserialization.

If the `speedups` extra is installed, aiohttp is installed with its own speedups extra.
Since aiobotocore and aioboto3 rely on aiohttp, this will also improve their 
performance.

## Installation

### Minimal installation:
```bash
pip install aio-lambda-api
```

### Installations with extras:

Multiple extra are provided

```bash
pip install aio-lambda-api[all]
```

* `all`: Install all extras.
* `aws`: Install AWS SDK (`aioboto3`).
* `validation`: Install input validation dependencies (`pydantic`).
* `speedups`: Input performance speedups dependencies (`uvloop`, `orjson`).
