from __future__ import annotations

import os
from typing import Mapping

from .base_api_client import BaseApiClient


class CryptoQuantClient(BaseApiClient):
    provider_name = "cryptoquant"
    default_base_url = "https://api.cryptoquant.com"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 20) -> None:
        resolved_key = api_key or os.getenv("CRYPTOQUANT_API_KEY")
        if not resolved_key:
            raise ValueError("Missing CRYPTOQUANT_API_KEY environment variable")
        super().__init__(
            base_url=base_url or self.default_base_url,
            api_key=resolved_key,
            timeout=timeout,
        )

    def build_headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}", **self.default_headers}
        if extra_headers:
            headers.update(extra_headers)
        return headers
