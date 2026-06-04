from __future__ import annotations

import os
from typing import Mapping

from .base_api_client import BaseApiClient


class CryptoQuantClient(BaseApiClient):
    provider_name = "cryptoquant"

    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 20, **kwargs) -> None:
        cryptoquant_api_key = api_key or os.getenv("CRYPTOQUANT_API_KEY")
        if not cryptoquant_api_key:
            raise ValueError("Missing CRYPTOQUANT_API_KEY environment variable")
        super().__init__(base_url=base_url, api_key=cryptoquant_api_key, timeout=timeout, **kwargs)

    def build_headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", **self.default_headers}
        headers["Authorization"] = f"Bearer {self.api_key}"
        if extra_headers:
            headers.update(extra_headers)
        return headers
