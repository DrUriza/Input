from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from input.input.coinglass_client import CoinGlassClient
from input.main.pipeline import DEFAULT_ENDPOINTS_PATH, DEFAULT_PROVIDER_BASE_URLS, Pipeline, ProviderEndpointRecord

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

EXPECTED_ERROR_KEYWORDS = (
    "plan",
    "subscription",
    "permission",
    "forbidden",
    "unauthorized",
    "upgrade",
    "quota",
    "rate limit",
    "too many requests",
    "api key",
)


@dataclass
class LiveEndpointResult:
    endpoint_id: str
    path: str
    status: str
    status_code: int | None
    message: str


def _contains_expected_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in EXPECTED_ERROR_KEYWORDS)


def _needs_interval(path: str) -> bool:
    return any(token in path for token in ("history", "ohlc", "chart"))


def _supports_limit(path: str) -> bool:
    return any(token in path for token in ("history", "list", "chart", "ohlc"))


def _is_aggregated_coin_based(path: str) -> bool:
    return "aggregated" in path or "/coin/" in path or "coins-" in path


def _build_params(record: ProviderEndpointRecord) -> dict[str, Any]:
    path = record.path.lower()
    params: dict[str, Any] = {}

    for required in record.required_params:
        if required == "symbol":
            if "/option/" in path:
                params[required] = DEFAULT_SYMBOL_COIN
            elif _is_aggregated_coin_based(path):
                params[required] = DEFAULT_SYMBOL_COIN
            elif "/futures/" in path or "/spot/" in path:
                params[required] = DEFAULT_SYMBOL_PAIR
            else:
                params[required] = DEFAULT_SYMBOL_COIN
        elif required == "exchange":
            params[required] = "Deribit" if "/option/" in path else DEFAULT_EXCHANGE
        elif required == "interval":
            params[required] = DEFAULT_INTERVAL
        elif required == "limit":
            params[required] = DEFAULT_LIMIT
        elif required in {"start_time", "end_time"}:
            params[required] = 0
        else:
            params[required] = DEFAULT_SYMBOL_COIN

    if "interval" not in params and _needs_interval(path):
        params["interval"] = DEFAULT_INTERVAL
    if "limit" not in params and _supports_limit(path):
        params["limit"] = DEFAULT_LIMIT

    return params


def _classify_response(status_code: int | None, response_text: str, ok: bool) -> tuple[str, str]:
    if ok:
        return ("SUCCESS", "HTTP success response")

    message = response_text or "No response text"

    if status_code == 401:
        return ("EXPECTED_AUTH_ERROR", message)
    if status_code == 403:
        return ("EXPECTED_PLAN_OR_PERMISSION_ERROR", message)
    if status_code == 429:
        return ("EXPECTED_RATE_LIMIT", message)
    if status_code == 400 and _contains_expected_keyword(message):
        return ("EXPECTED_PROVIDER_BAD_REQUEST", message)

    if status_code == 404:
        return ("UNEXPECTED_ERROR", "HTTP 404 suggests wrong path or malformed URL")
    if status_code is None:
        return ("UNEXPECTED_ERROR", "Missing HTTP status_code")

    return ("UNEXPECTED_ERROR", f"Unhandled provider response status_code={status_code}, body={message}")


def test_live_coinglass_p1_endpoints_from_registry_return_expected_status() -> None:
    api_key = os.getenv("COINGLASS_API_KEY")
    assert api_key is not None and api_key.strip()

    pipeline = Pipeline(endpoints_path=DEFAULT_ENDPOINTS_PATH)
    p1_coinglass_records = [
        record
        for record in pipeline._records.values()
        if record.provider == "coinglass" and record.priority == "P1"
    ]

    assert p1_coinglass_records, "No P1 CoinGlass endpoints found in End_Points.json"
    assert all(record.provider != "binance" for record in p1_coinglass_records)

    client = CoinGlassClient(
        base_url=DEFAULT_PROVIDER_BASE_URLS["coinglass"],
        api_key=api_key,
        timeout=25,
    )

    results: list[LiveEndpointResult] = []
    unexpected_messages: list[str] = []

    for record in p1_coinglass_records:
        if not record.path.startswith("/api/"):
            unexpected_messages.append(f"{record.endpoint_id}: malformed path {record.path}")
            continue

        params = _build_params(record)

        try:
            response = client.fetch_raw(record.to_endpoint_spec(), params)
        except Exception as exc:  # noqa: BLE001
            unexpected_messages.append(f"{record.endpoint_id}: transport/provider exception {type(exc).__name__}: {exc}")
            continue

        status, message = _classify_response(response.status_code, response.text, response.ok)
        results.append(
            LiveEndpointResult(
                endpoint_id=record.endpoint_id,
                path=record.path,
                status=status,
                status_code=response.status_code,
                message=message,
            )
        )

        if status == "UNEXPECTED_ERROR":
            unexpected_messages.append(f"{record.endpoint_id}: {message}")

    summary = {
        "total": len(p1_coinglass_records),
        "success": sum(1 for result in results if result.status == "SUCCESS"),
        "expected_auth": sum(1 for result in results if result.status == "EXPECTED_AUTH_ERROR"),
        "expected_plan_or_permission": sum(
            1 for result in results if result.status == "EXPECTED_PLAN_OR_PERMISSION_ERROR"
        ),
        "expected_rate_limit": sum(1 for result in results if result.status == "EXPECTED_RATE_LIMIT"),
        "expected_bad_request": sum(1 for result in results if result.status == "EXPECTED_PROVIDER_BAD_REQUEST"),
        "unexpected": sum(1 for result in results if result.status == "UNEXPECTED_ERROR") + len(unexpected_messages),
    }

    print("\\nCoinGlass P1 integration summary:")
    print(summary)

    if unexpected_messages:
        pytest.fail("Unexpected CoinGlass integration failures:\n" + "\n".join(unexpected_messages))
