"""API base."""
from asyncio import new_event_loop as _new_event_loop, wait_for as _wait_for
from base64 import b64encode as _b64encode
from contextlib import AsyncExitStack as _AsyncExitStack
from inspect import signature as _signature
from typing import (
    Any as _Any,
    AsyncContextManager as _AsyncContextManager,
    TypeVar as _TypeVar,
    Dict as _Dict,
    Callable as _Callable,
    Optional as _Optional,
    Coroutine as _Coroutine,
    Type as _Type,
    Tuple as _Tuple,
)

try:
    from pydantic import validate_arguments as _validate_arguments
except ImportError:
    _validate_arguments = None  # type: ignore

from aio_lambda_api.exceptions import (
    HTTPException as _HttpException,
    ValidationError as _ValidationError,
)
from aio_lambda_api.responses import (
    Response as _Response,
    JSONResponse as _JSONResponse,
)
from aio_lambda_api.requests import Request as _Request
from aio_lambda_api.json import dumps as _dumps
from aio_lambda_api.logging import logger as _logger, context_log as _context_log
from aio_lambda_api.settings import FUNCTION_TIMEOUT as _FUNCTION_TIMEOUT
from aio_lambda_api.status import get_status_message as _get_status_message


_T = _TypeVar("_T")

_VALIDATOR_CONFIG = dict(arbitrary_types_allowed=True)


class _APIRoute:
    """API route."""

    __slots__ = ["status_code", "func", "params"]

    def __init__(
        self,
        func: _Callable[..., _Any],
        status_code: int,
        params: _Dict[str, _Type[_Any]],
    ) -> None:
        self.status_code = status_code
        self.func = func
        self.params = params


class Handler:
    """Serverless function handler."""

    __slots__ = ["_loop", "_exit_stack", "_routes"]

    def __init__(self) -> None:
        self._loop = _new_event_loop()
        self._exit_stack = _AsyncExitStack()
        self._routes: _Dict[str, _Dict[str, _APIRoute]] = dict()

    def __del__(self) -> None:
        self.run_async(self._exit_stack.__aexit__(None, None, None))

    def __call__(self, event: _Dict[str, _Any], context: _Any) -> _Dict[str, _Any]:
        """AWS Lambda entry point.

        Args:
            event: Lambda event.
            context: Lambda context.

        Returns:
            API Gateway compatible HTTP response.
        """
        method, path = self._get_route_from_event(event)
        with _logger(context.aws_request_id) as log:
            try:
                log["method"] = method
                log["path"] = path

                request, response, func = self._prepare_request(
                    path, method, event, context
                )

                try:
                    log["request_id"] = request.headers["x-request-id"]
                except KeyError:
                    log["request_id"] = event["requestContext"]["requestId"]
                try:
                    log["user_agent"] = request.headers["user-agent"]
                except KeyError:
                    pass

                return self._call_route_function(func, response)

            except _HttpException as exception:
                error_detail = exception.error_detail
                if error_detail:
                    log["error_detail"] = error_detail
                log["status_code"] = exception.status_code
                if exception.status_code >= 500:
                    log["level"] = "error"
                elif exception.status_code >= 400:
                    log["level"] = "warning"
                return self._prepare_response(
                    _JSONResponse(
                        content=dict(detail=exception.detail),
                        status_code=exception.status_code,
                    )
                )

            except _ValidationError as exception:
                errors = exception.errors()
                log["error_detail"] = _dumps(errors)
                log["status_code"] = 422
                log["level"] = "warning"
                return self._prepare_response(
                    _JSONResponse(content=dict(detail=errors), status_code=422)
                )

    @staticmethod
    def _get_route_from_event(event: _Dict[str, _Any]) -> _Tuple[str, str]:
        """Get route from lambda event.

        References:
            https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html

        Args:
            event: Lambda event.

        Returns:
            Route method and path
        """
        request_context = event["requestContext"]
        try:
            # HTTP API
            http = request_context["http"]
        except KeyError:
            # REST API
            return request_context["httpMethod"], request_context["path"]
        return http["method"], http["path"]

    def _prepare_request(
        self, path: str, method: str, event: _Dict[str, _Any], context: _Dict[str, _Any]
    ) -> _Tuple[_Request, _Response, _Coroutine[_Any, _Any, _Any]]:
        """Prepare the request.

        Args:
            path: HTTP path.
            method: HTTP method.
            event: Request event.
            context: AWS lambda context.

        Returns:
            Request object, Default response object, Route function coroutine.
        """
        try:
            path_routes = self._routes[path]
        except KeyError:
            raise _HttpException(404)
        try:
            route = path_routes[method]
        except KeyError:
            raise _HttpException(405)

        request = _Request(event, context)
        response = _JSONResponse(status_code=route.status_code)

        body = request.json()
        kwargs = body.copy() if isinstance(body, dict) else dict()
        for param_name, param_cls in route.params.items():
            if param_cls == _Request:
                kwargs[param_name] = request
            elif param_cls == _Response:
                kwargs[param_name] = response

        return request, response, route.func(**kwargs)

    def _call_route_function(
        self, func: _Coroutine[_Any, _Any, _Any], response: _Response
    ) -> _Dict[str, _Any]:
        """Call the route function and returns its response.

        Args:
            func: Route function.
            response: Response.

        Returns:
            API gateways compatible response.
        """
        content = self.run_async(_wait_for(func, _FUNCTION_TIMEOUT))
        if isinstance(content, _Response):
            response = content
        else:
            response.content = content
        return self._prepare_response(response)

    @staticmethod
    def _prepare_response(response: _Response) -> _Dict[str, _Any]:
        """Prepare the AWS lambda response.

        Args:
            response: Response.

        Returns:
            API gateways compatible response.
        """
        status_code = response.status_code
        headers = response.headers
        body = response.content
        is_base64_encoded = False

        if body is None:
            if status_code == 200:
                status_code = 204
            elif status_code >= 400:
                body = dict(details=_get_status_message(status_code))

        if body is not None:
            body = response.render(body)
            headers["content-length"] = str(len(body))

            if response.media_type is not None:
                headers["content-type"] = response.media_type

            if isinstance(body, (bytes, bytearray, memoryview)):
                body = _b64encode(body).decode()
                is_base64_encoded = True

        log = _context_log.get()
        log["status_code"] = status_code
        try:
            headers["x-request-id"] = log["request_id"]
        except KeyError:
            pass
        return dict(
            body=body,
            statusCode=str(status_code),
            headers=headers,
            isBase64Encoded=is_base64_encoded,
        )

    def enter_async_context(self, context: _AsyncContextManager[_T]) -> _T:
        """Initialize an async context manager.

        The context manager will be exited properly on API object destruction.

        Args:
            context: Async Object to initialize.

        Returns:
            Initialized object.
        """
        return self._loop.run_until_complete(
            self._exit_stack.enter_async_context(context)
        )

    def run_async(self, task: _Coroutine[_Any, _Any, _T]) -> _T:
        """Run an async task in the sync context.

        This can be used to call initialization functions outside the serverless
        function itself.

        Args:
            task: Async task.

        Returns:
            Task result.
        """
        return self._loop.run_until_complete(task)

    def _api_route(
        self,
        path: str,
        method: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register API route.

        Args:
            path: HTTP path.
            method: HTTP method.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """

        def decorator(func: _Callable[..., _Any]) -> _Callable[..., _Any]:
            """Decorator.

            Args:
                func: Route function.

            Returns:
                Route function.
            """
            params = self._check_signature(func)
            if _validate_arguments is not None:
                func = _validate_arguments(  # type: ignore
                    func, config=_VALIDATOR_CONFIG
                )
            try:
                path_routes = self._routes[path]
            except KeyError:
                path_routes = self._routes[path] = dict()
            try:
                path_routes[method]
            except KeyError:
                path_routes[method] = _APIRoute(
                    func=func, status_code=status_code or 200, params=params
                )
            else:
                raise ValueError(f'Route already registered: {method} "{path}".')
            return func

        return decorator

    @staticmethod
    def _check_signature(func: _Callable[..., _Any]) -> _Dict[str, _Type[_Any]]:
        """Check function signature and returns parameters to inject in functions calls.

        Args:
            func: Route function.

        Returns:
            Parameters to inject.
        """
        params: _Dict[str, _Type[_Any]] = dict()
        for param in _signature(func).parameters.values():
            annotation = param.annotation
            if isinstance(annotation, type) and issubclass(annotation, _Request):
                params[param.name] = _Request
            elif isinstance(annotation, type) and issubclass(annotation, _Response):
                params[param.name] = _Response
        return params

    def delete(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a DELETE route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="DELETE", status_code=status_code)

    def get(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a GET route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="GET", status_code=status_code)

    def head(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a HEAD route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="HEAD", status_code=status_code)

    def options(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a OPTIONS route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="OPTIONS", status_code=status_code)

    def patch(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a PATCH route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="PATCH", status_code=status_code)

    def post(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a POST route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="POST", status_code=status_code)

    def put(
        self,
        path: str,
        *,
        status_code: _Optional[int] = None,
    ) -> _Callable[[_Callable[..., _Any]], _Callable[..., _Any]]:
        """Register a PUT route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="PUT", status_code=status_code)
