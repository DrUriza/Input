from __future__ import annotations

import os
from typing import Mapping

from .base_api_client import BaseApiClient


class CoinGlassClient(BaseApiClient):
    provider_name = "coinglass"
    default_base_url = "https://open-api-v4.coinglass.com"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 20) -> None:
        resolved_key = api_key or os.getenv("COINGLASS_API_KEY")
        if not resolved_key:
            raise ValueError("Missing COINGLASS_API_KEY environment variable")
        super().__init__(
            base_url=base_url or self.default_base_url,
            api_key=resolved_key,
            timeout=timeout,
        )

    def build_headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"accept": "application/json", "CG-API-KEY": self.api_key, **self.default_headers}
        if extra_headers:
            headers.update(extra_headers)
        return headers
