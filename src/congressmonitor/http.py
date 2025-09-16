from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


DEFAULT_HEADERS = {
    "User-Agent": "congressmonitor/0.1",
}


class HTTPError(RuntimeError):
    """Raised when an HTTP request fails in a non-recoverable way."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Response:
    status_code: int
    content: bytes

    def json(self) -> Any:
        try:
            text = self.content.decode("utf-8")
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
            raise ValueError("Response did not contain valid JSON") from exc

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"HTTP request failed with status {self.status_code}", status=self.status_code)


class SimpleHttpClient:
    """Minimal HTTP client used to retrieve JSON documents."""

    def get(self, url: str, timeout: int = 60) -> Response:
        req = request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with request.urlopen(req, timeout=timeout) as handle:
                status = getattr(handle, "status", handle.getcode())
                data = handle.read()
                return Response(status_code=status, content=data)
        except error.HTTPError as exc:
            body = exc.read()
            return Response(status_code=exc.code, content=body)
        except error.URLError as exc:  # pragma: no cover - network failure
            raise HTTPError(f"Failed to retrieve {url}: {exc.reason}") from exc


__all__ = ["SimpleHttpClient", "HTTPError", "Response"]
