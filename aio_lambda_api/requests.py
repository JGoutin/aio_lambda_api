"""Requests."""
from base64 import b64decode as _b64decode
from typing import (
    Dict as _Dict,
    Any as _Any,
    Iterator as _Iterator,
    Mapping as _Mapping,
    Optional as _Optional,
)
from aio_lambda_api.json import loads as _loads, JSONDecodeError as _JSONDecodeError


class Request(_Mapping[str, _Any]):
    """Request."""

    __slots__ = ["scope", "_headers", "_body", "_json"]

    def __init__(self, event: _Dict[str, _Any], context: _Dict[str, _Any]) -> None:
        self.scope = dict(event=event, context=context)

    def __getitem__(self, key: str) -> _Any:
        return self.scope[key]

    def __iter__(self) -> _Iterator[_Any]:
        return iter(self.scope)

    def __len__(self) -> int:
        return len(self.scope)

    @property
    def headers(self) -> _Dict[str, str]:
        """HTTP headers.

        Returns:
            Headers.
        """
        try:
            return self._headers
        except AttributeError:
            self._headers: _Dict[str, str] = {
                key.lower(): value
                for key, value in self.scope["event"]["headers"].items()
            }
            return self._headers

    def body(self) -> _Optional[bytes]:
        """Body.

        Returns:
            Body.
        """
        try:
            return self._body
        except AttributeError:
            body = self.scope["event"].get("body")
            if body is not None:
                body = body.encode()
                if self.scope["event"].get("isBase64Encoded", False):
                    body = _b64decode(body)
            self._body: _Optional[bytes] = body
            return body  # type: ignore

    def json(self) -> _Any:
        """JSON body.

        Returns:
            JSON deserialized body.
        """
        try:
            return self._json
        except AttributeError:
            body = self.body()
            if body is not None:
                try:
                    body = _loads(body)
                except _JSONDecodeError:
                    pass
            self._json: _Any = body
            return body
