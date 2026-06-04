from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from input.input.coinglass.coinglass_client import CoinGlassClient
from input.input.coinglass.coinglass_endpoints import CoinGlassEndpointCatalog, EndpointContract
from input.input.coinglass.coinglass_models import CoinGlassRequest
from input.input.cryptoquant.errors import InputProviderError, InputValidationError
from input.input.cryptoquant.schemas import SourceStatus

pytestmark = pytest.mark.integration

if not os.getenv("RUN_COINGLASS_INTEGRATION_TESTS"):
    pytest.skip(
        "CoinGlass integration tests disabled. Set RUN_COINGLASS_INTEGRATION_TESTS=1.",
        allow_module_level=True,
    )

if not os.getenv("COINGLASS_API_KEY"):
    pytest.skip("Missing COINGLASS_API_KEY.", allow_module_level=True)


DEFAULT_EXCHANGE = "Binance"
DEFAULT_SYMBOL_PAIR = "BTCUSDT"
DEFAULT_SYMBOL_COIN = "BTC"
DEFAULT_INTERVAL = "1h"
DEFAULT_LIMIT = 1

EXPECTED_PLAN_ERROR_KEYWORDS = [
    "plan",
    "subscription",
    "permission",
    "permissions",
    "forbidden",
    "unauthorized",
    "not authorized",
    "access",
    "upgrade",
    "quota",
    "rate limit",
    "too many requests",
    "api key",
    "key",
]

P1_SMOKE_TEST_OVERRIDES: dict[str, dict[str, Any]] = {
    # Add endpoint specific fixes here when provider contracts require stricter params.
}


@dataclass
class LiveEndpointResult:
    endpoint_key: str
    path: str
    priority: str
    category: str
    status: str
    status_code: int | None
    message: str


class TrackingCatalog:
    def __init__(self, catalog: CoinGlassEndpointCatalog) -> None:
        self._catalog = catalog
        self.require_contract_calls: dict[str, int] = {}
        self.require_url_calls: dict[str, int] = {}
        self.base_url = catalog.base_url

    def require_contract(self, endpoint_key: str) -> EndpointContract:
        self.require_contract_calls[endpoint_key] = self.require_contract_calls.get(endpoint_key, 0) + 1
        return self._catalog.require_contract(endpoint_key)

    def require_url(self, endpoint_key: str) -> str:
        self.require_url_calls[endpoint_key] = self.require_url_calls.get(endpoint_key, 0) + 1
        return self._catalog.require_url(endpoint_key)


def _contains_expected_provider_keyword(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in EXPECTED_PLAN_ERROR_KEYWORDS)


def _needs_interval(path: str) -> bool:
    return any(token in path for token in ("history", "ohlc", "chart"))


def _supports_limit(path: str) -> bool:
    return any(token in path for token in ("history", "list", "chart", "ohlc"))


def _is_aggregated_coin_based(path: str) -> bool:
    return "aggregated" in path or "/coin/" in path or "coins-" in path


def build_smoke_request_for_contract(contract: EndpointContract) -> CoinGlassRequest:
    override = P1_SMOKE_TEST_OVERRIDES.get(contract.key, {})

    if override:
        return CoinGlassRequest(
            endpoint_key=contract.key,
            symbol=override.get("symbol"),
            exchange=override.get("exchange"),
            interval=override.get("interval"),
            limit=override.get("limit"),
            params=override.get("params", {}),
        )

    path = contract.path.lower()
    params: dict[str, Any] = {}
    symbol: str | None = None
    exchange: str | None = None
    interval: str | None = None
    limit: int | None = None

    if "supported-" in path:
        return CoinGlassRequest(endpoint_key=contract.key)

    if "/option/" in path:
        symbol = DEFAULT_SYMBOL_COIN
        exchange = "Deribit"
    elif "/etf/bitcoin" in path or "/index/" in path or "coinbase-premium" in path:
        symbol = None
        exchange = None
    elif "/futures/" in path:
        if _is_aggregated_coin_based(path):
            symbol = DEFAULT_SYMBOL_COIN
        else:
            symbol = DEFAULT_SYMBOL_PAIR
            exchange = DEFAULT_EXCHANGE
    elif "/spot/" in path:
        if _is_aggregated_coin_based(path):
            symbol = DEFAULT_SYMBOL_COIN
        else:
            symbol = DEFAULT_SYMBOL_PAIR
            exchange = DEFAULT_EXCHANGE

    if _needs_interval(path):
        interval = DEFAULT_INTERVAL

    if _supports_limit(path):
        limit = DEFAULT_LIMIT

    return CoinGlassRequest(
        endpoint_key=contract.key,
        symbol=symbol,
        exchange=exchange,
        interval=interval,
        limit=limit,
        params=params,
    )


def _classify_payload_response(status_code: int | None, response_text: str, payload_status: SourceStatus, data: Any) -> tuple[str, str]:
    if payload_status == SourceStatus.OK:
        if data is None:
            return ("UNEXPECTED_ERROR", "Provider returned OK but payload data is None")
        return ("SUCCESS", "HTTP 200 provider response")

    message = response_text or "No response text"

    if status_code == 401:
        return ("EXPECTED_AUTH_ERROR", message)

    if status_code == 403:
        return ("EXPECTED_PLAN_OR_PERMISSION_ERROR", message)

    if status_code == 429:
        return ("EXPECTED_RATE_LIMIT", message)

    if status_code == 400:
        if _contains_expected_provider_keyword(message):
            return ("EXPECTED_PROVIDER_BAD_REQUEST", message)
        return (
            "UNEXPECTED_ERROR",
            f"HTTP 400 without plan/permission style keywords. Response: {message}",
        )

    if status_code == 404:
        return ("UNEXPECTED_ERROR", "HTTP 404 suggests wrong path or malformed URL")

    if status_code is None:
        return ("UNEXPECTED_ERROR", "Missing HTTP status_code in metadata")

    return (
        "UNEXPECTED_ERROR",
        f"Unhandled provider response status_code={status_code}, body={message}",
    )


def test_live_coinglass_p1_endpoints_return_success_or_expected_plan_error() -> None:
    api_key = os.getenv("COINGLASS_API_KEY")
    assert api_key is not None and api_key.strip()

    catalog = CoinGlassEndpointCatalog()
    p1_contracts = catalog.get_contracts_for_execution("P1")
    tracking_catalog = TrackingCatalog(catalog)
    client = CoinGlassClient(api_key=api_key, endpoint_catalog=tracking_catalog, timeout=25)

    results: list[LiveEndpointResult] = []
    unexpected_messages: list[str] = []

    for contract in p1_contracts:
        endpoint_key = contract.key

        try:
            resolved_contract = catalog.require_contract(endpoint_key)
        except KeyError as exc:
            pytest.fail(f"Catalog could not resolve valid P1 endpoint '{endpoint_key}': {exc}")

        url = catalog.require_url(endpoint_key)
        if not url.startswith(catalog.base_url):
            pytest.fail(f"Catalog URL does not start with base URL for '{endpoint_key}': {url}")

        if not resolved_contract.path.startswith("/api/"):
            pytest.fail(f"Malformed path for endpoint '{endpoint_key}': {resolved_contract.path}")

        request = build_smoke_request_for_contract(resolved_contract)

        try:
            payload = client.fetch_endpoint(request)
        except InputValidationError as exc:
            results.append(
                LiveEndpointResult(
                    endpoint_key=endpoint_key,
                    path=resolved_contract.path,
                    priority=resolved_contract.priority,
                    category=resolved_contract.category,
                    status="UNEXPECTED_ERROR",
                    status_code=None,
                    message=f"InputValidationError for valid catalog endpoint: {exc}",
                )
            )
            unexpected_messages.append(f"{endpoint_key}: InputValidationError {exc}")
            continue
        except InputProviderError as exc:
            results.append(
                LiveEndpointResult(
                    endpoint_key=endpoint_key,
                    path=resolved_contract.path,
                    priority=resolved_contract.priority,
                    category=resolved_contract.category,
                    status="UNEXPECTED_ERROR",
                    status_code=None,
                    message=f"Transport/provider exception before classified response: {exc}",
                )
            )
            unexpected_messages.append(f"{endpoint_key}: InputProviderError {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            results.append(
                LiveEndpointResult(
                    endpoint_key=endpoint_key,
                    path=resolved_contract.path,
                    priority=resolved_contract.priority,
                    category=resolved_contract.category,
                    status="UNEXPECTED_ERROR",
                    status_code=None,
                    message=f"Unexpected exception type {type(exc).__name__}: {exc}",
                )
            )
            unexpected_messages.append(f"{endpoint_key}: {type(exc).__name__} {exc}")
            continue

        if tracking_catalog.require_contract_calls.get(endpoint_key, 0) == 0:
            results.append(
                LiveEndpointResult(
                    endpoint_key=endpoint_key,
                    path=resolved_contract.path,
                    priority=resolved_contract.priority,
                    category=resolved_contract.category,
                    status="UNEXPECTED_ERROR",
                    status_code=None,
                    message="Request was not routed through catalog.require_contract",
                )
            )
            unexpected_messages.append(f"{endpoint_key}: missing require_contract routing")
            continue

        if tracking_catalog.require_url_calls.get(endpoint_key, 0) == 0:
            results.append(
                LiveEndpointResult(
                    endpoint_key=endpoint_key,
                    path=resolved_contract.path,
                    priority=resolved_contract.priority,
                    category=resolved_contract.category,
                    status="UNEXPECTED_ERROR",
                    status_code=None,
                    message="Request was not routed through catalog.require_url",
                )
            )
            unexpected_messages.append(f"{endpoint_key}: missing require_url routing")
            continue

        metadata = dict(payload.metadata or {})
        status_code = metadata.get("status_code")
        response_text = str(metadata.get("response_text", ""))
        status, message = _classify_payload_response(status_code, response_text, payload.status, payload.data)

        results.append(
            LiveEndpointResult(
                endpoint_key=endpoint_key,
                path=resolved_contract.path,
                priority=resolved_contract.priority,
                category=resolved_contract.category,
                status=status,
                status_code=status_code if isinstance(status_code, int) else None,
                message=message,
            )
        )

        if status == "UNEXPECTED_ERROR":
            unexpected_messages.append(f"{endpoint_key}: {message}")

    success_count = sum(1 for result in results if result.status == "SUCCESS")
    plan_error_count = sum(1 for result in results if result.status == "EXPECTED_PLAN_OR_PERMISSION_ERROR")
    auth_error_count = sum(1 for result in results if result.status == "EXPECTED_AUTH_ERROR")
    rate_limit_count = sum(1 for result in results if result.status == "EXPECTED_RATE_LIMIT")
    provider_bad_request_count = sum(1 for result in results if result.status == "EXPECTED_PROVIDER_BAD_REQUEST")
    unexpected_error_count = sum(1 for result in results if result.status == "UNEXPECTED_ERROR")
    tested_endpoint_keys = [result.endpoint_key for result in results]

    summary = {
        "success_count": success_count,
        "plan_error_count": plan_error_count,
        "auth_error_count": auth_error_count,
        "rate_limit_count": rate_limit_count,
        "provider_bad_request_count": provider_bad_request_count,
        "unexpected_error_count": unexpected_error_count,
        "tested_endpoint_keys": tested_endpoint_keys,
    }

    print("\\nCoinGlass P1 integration summary:")
    print(summary)

    if P1_SMOKE_TEST_OVERRIDES:
        print("Configured endpoint overrides:", sorted(P1_SMOKE_TEST_OVERRIDES.keys()))

    if unexpected_messages:
        pytest.fail(
            "Unexpected CoinGlass integration failures:\n"
            + "\n".join(unexpected_messages)
            + f"\nSummary: {summary}"
        )
