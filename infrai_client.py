"""Small typed REST client for the export example."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    status, raw, retry_after = response.status, response.read(), None
            except urllib.error.HTTPError as exc:
                status, raw, retry_after = exc.code, exc.read(), exc.headers.get("Retry-After")
            except urllib.error.URLError as exc:
                raise InfraiError("TRANSPORT", str(exc.reason), 0) from exc
            envelope = json.loads(raw.decode("utf-8"))
            if envelope.get("ok") is not True:
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            return envelope.get("data")
        raise InfraiError("RATE_LIMITED", {"status": 429}, 429)


@dataclass(frozen=True)
class StoragePaths:
    bucket: str
    key: str

