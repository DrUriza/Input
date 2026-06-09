from __future__ import annotations

from typing import Any, Mapping

import requests

from input.processing.raw_response_contracts import EndpointSpecContract, RawResponseContract


class RequestRetryPolicy:
    def __init__(self, attempts: int = 1, retry_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)) -> None:
        self.attempts = attempts
        self.retry_status_codes = retry_status_codes


class BaseApiClient:
    provider_name = "unknown"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 20,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.default_headers = dict(default_headers or {})
        self.session = requests.Session()
        self.retry_policy = RequestRetryPolicy()

    def build_url(self, path: str = "") -> str:
        if not path:
            return self.base_url
        return f"{self.base_url}{path if path.startswith('/') else '/' + path}"

    def build_headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = dict(self.default_headers)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def describe_connection(self) -> dict[str, str | int | bool]:
        return {
            "provider": self.provider_name,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "has_api_key": bool(self.api_key),
        }

    def fetch_raw(self, endpoint: EndpointSpecContract, params: Mapping[str, Any] | None = None) -> RawResponseContract:
        if endpoint.provider != self.provider_name:
            raise ValueError(f"Client '{self.provider_name}' cannot execute provider '{endpoint.provider}'")

        request_params = dict(params or {})
        url = self.build_url(endpoint.path)
        headers = self.build_headers()
        last_exception: Exception | None = None
        response: requests.Response | None = None

        for attempt in range(self.retry_policy.attempts + 1):
            try:
                response = self.session.request(
                    method=endpoint.method,
                    url=url,
                    headers=headers,
                    params=request_params,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_exception = exc
                continue

            if response.ok or response.status_code not in self.retry_policy.retry_status_codes:
                break

        if response is None:
            assert last_exception is not None
            raise RuntimeError(f"Transport failure for {endpoint.endpoint_id}: {last_exception}") from last_exception

        data: Any = None
        try:
            data = response.json()
        except ValueError:
            data = None

        return RawResponseContract(
            endpoint_id=endpoint.endpoint_id,
            provider=endpoint.provider,
            url=url,
            method=endpoint.method,
            status_code=response.status_code,
            ok=response.ok,
            headers=dict(response.headers),
            text=response.text,
            data=data,
            params=request_params,
            metadata={
                "attempts": attempt + 1,
                "base_url": self.base_url,
                "ttl_seconds": endpoint.ttl_seconds,
                "priority": endpoint.priority,
                "family": endpoint.family,
                "output_type": endpoint.output_type,
            },
        )
