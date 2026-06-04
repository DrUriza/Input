from __future__ import annotations

import os

from .base_api_client import BaseApiClient


class CoinGlassClient(BaseApiClient):
    provider_name = "coinglass"

    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 20, **kwargs) -> None:
        coinglass_api_key = api_key or os.getenv("COINGLASS_API_KEY")
        if not coinglass_api_key:
            raise ValueError("Missing COINGLASS_API_KEY environment variable")
        super().__init__(base_url=base_url, api_key=coinglass_api_key, timeout=timeout, **kwargs)
