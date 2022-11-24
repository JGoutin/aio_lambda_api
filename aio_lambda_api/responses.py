"""Responses."""
from typing import Optional as _Optional, Any as _Any, Dict as _Dict, Union as _Union
from aio_lambda_api.json import dumps as _dumps


class Response:
    """Response."""

    media_type = None
    charset = "utf-8"

    def __init__(
        self,
        content: _Optional[_Any] = None,
        status_code: int = 200,
        headers: _Optional[_Dict[str, str]] = None,
        media_type: _Optional[str] = None,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = headers or dict()
        if media_type is not None:
            self.media_type = media_type

    def render(self, content: _Any) -> _Union[str, bytes, bytearray, memoryview]:
        """Render content for response in str or bytes.

        Bytes content will be returned base64 encoded in the final response.

        Args:
            content: Body content.

        Returns:
            Rendered content.
        """
        return content  # type: ignore


class JSONResponse(Response):
    """JSON Response."""

    media_type = "application/json"

    def render(self, content: _Any) -> str:
        """Render content for response in JSON str.

        Args:
            content: Body content.

        Returns:
            JSON content.
        """
        return _dumps(content)
