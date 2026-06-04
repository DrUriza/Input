from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from input.input.coinglass.coinglass_client import CoinGlassClient
from input.input.coinglass.coinglass_endpoints import CoinGlassEndpointCatalog, EndpointContract
from input.input.coinglass.coinglass_models import CoinGlassRequest
from input.input.cryptoquant.errors import InputValidationError
from input.input.cryptoquant.schemas import RawInputPayload, SourceRequest, SourceStatus


def write_catalog(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "Coinglass_Endpoint.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class DummyResponse:
    def __init__(self, *, ok: bool = True, status_code: int = 200, payload: Any = None, text: str = "") -> None:
        self.ok = ok
        self.status_code = status_code
        self._payload = payload if payload is not None else {"data": []}
        self.text = text

    def json(self) -> Any:
        return self._payload


class StubCatalog:
    def __init__(self, contract: EndpointContract, url: str, *, fail_contract_lookup: bool = False) -> None:
        self.contract = contract
        self.url = url
        self.base_url = "https://stub.coinglass.local"
        self.fail_contract_lookup = fail_contract_lookup
        self.require_contract_calls: list[str] = []
        self.require_url_calls: list[str] = []

    def require_contract(self, endpoint_key: str) -> EndpointContract:
        self.require_contract_calls.append(endpoint_key)
        if self.fail_contract_lookup:
            raise KeyError(endpoint_key)
        return self.contract

    def require_url(self, endpoint_key: str) -> str:
        self.require_url_calls.append(endpoint_key)
        return self.url


def test_catalog_loads_default_json() -> None:
    catalog = CoinGlassEndpointCatalog()

    contract = catalog.require_contract("futures_orderbook_large_limit_order")

    assert catalog.contains("futures_orderbook_large_limit_order")
    assert contract.priority == "P1"
    assert contract.path.startswith("/api/")


def test_catalog_has_p1_p2_p3() -> None:
    catalog = CoinGlassEndpointCatalog()

    summary = catalog.summary()

    assert set(summary) == {"P1", "P2", "P3"}
    assert all(count > 0 for count in summary.values())


def test_catalog_rejects_missing_required_fields(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path,
        {
            "P1": {
                "missing_fields": {
                    "path": "/api/test/path",
                    "category": "test",
                    "priority": "P1",
                    "use": "test",
                }
            },
            "P2": {},
            "P3": {},
        },
    )

    with pytest.raises(ValueError, match="missing required fields"):
        CoinGlassEndpointCatalog(catalog_path)


def test_catalog_rejects_priority_mismatch(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path,
        {
            "P1": {
                "priority_mismatch": {
                    "path": "/api/test/path",
                    "category": "test",
                    "priority": "P2",
                    "use": "test",
                    "cache_ttl_sec": 1,
                }
            },
            "P2": {},
            "P3": {},
        },
    )

    with pytest.raises(ValueError, match="declares 'P2'"):
        CoinGlassEndpointCatalog(catalog_path)


def test_catalog_rejects_duplicate_keys(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path,
        {
            "P1": {
                "duplicate_key": {
                    "path": "/api/test/path-1",
                    "category": "test",
                    "priority": "P1",
                    "use": "test",
                    "cache_ttl_sec": 1,
                }
            },
            "P2": {
                "duplicate_key": {
                    "path": "/api/test/path-2",
                    "category": "test",
                    "priority": "P2",
                    "use": "test",
                    "cache_ttl_sec": 1,
                }
            },
            "P3": {},
        },
    )

    with pytest.raises(ValueError, match="Duplicated endpoint key"):
        CoinGlassEndpointCatalog(catalog_path)


def test_catalog_rejects_invalid_path_without_api_prefix(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path,
        {
            "P1": {
                "invalid_path": {
                    "path": "/v1/not-allowed",
                    "category": "test",
                    "priority": "P1",
                    "use": "test",
                    "cache_ttl_sec": 1,
                }
            },
            "P2": {},
            "P3": {},
        },
    )

    with pytest.raises(ValueError, match="starting with /api/"):
        CoinGlassEndpointCatalog(catalog_path)


def test_catalog_rejects_negative_cache_ttl(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path,
        {
            "P1": {
                "negative_ttl": {
                    "path": "/api/test/path",
                    "category": "test",
                    "priority": "P1",
                    "use": "test",
                    "cache_ttl_sec": -1,
                }
            },
            "P2": {},
            "P3": {},
        },
    )

    with pytest.raises(ValueError, match="cache_ttl_sec >= 0"):
        CoinGlassEndpointCatalog(catalog_path)


def test_require_url_uses_json_contract() -> None:
    catalog = CoinGlassEndpointCatalog()

    contract = catalog.require_contract("futures_orderbook_large_limit_order")
    url = catalog.require_url("futures_orderbook_large_limit_order")

    assert url == f"{catalog.base_url}{contract.path}"
    assert url.endswith(contract.path)


def test_get_by_priority_returns_only_selected_priority() -> None:
    catalog = CoinGlassEndpointCatalog()

    contracts = catalog.get_by_priority("P2")

    assert contracts
    assert all(contract.priority == "P2" for contract in contracts.values())
    assert len(contracts) == catalog.summary()["P2"]


def test_client_uses_catalog_require_url(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = EndpointContract(
        key="futures_orderbook_large_limit_order",
        path="/api/futures/orderbook/large-limit-order",
        category="whale_orderbook",
        priority="P1",
        use="current_large_limit_orders_for_whale_orderbook_detection",
        cache_ttl_sec=15,
    )
    stub_catalog = StubCatalog(contract=contract, url="https://stub.coinglass.local/api/futures/orderbook/large-limit-order")
    captured: dict[str, Any] = {}

    def fake_get(url: str, headers: dict[str, str], params: dict[str, Any], timeout: int) -> DummyResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return DummyResponse(ok=True, status_code=200, payload={"ok": True})

    monkeypatch.setattr("input.input.coinglass.coinglass_client.requests.get", fake_get)

    client = CoinGlassClient(api_key="test-key", endpoint_catalog=stub_catalog, timeout=9)
    payload = client.fetch_endpoint(CoinGlassRequest(endpoint_key=contract.key, symbol="BTC"))

    assert stub_catalog.require_contract_calls == [contract.key]
    assert stub_catalog.require_url_calls == [contract.key]
    assert captured["url"] == stub_catalog.url
    assert payload.status == SourceStatus.OK


def test_client_rejects_unknown_endpoint_key() -> None:
    contract = EndpointContract(
        key="known",
        path="/api/known",
        category="test",
        priority="P1",
        use="test",
        cache_ttl_sec=1,
    )
    stub_catalog = StubCatalog(contract=contract, url="https://stub.coinglass.local/api/known", fail_contract_lookup=True)
    client = CoinGlassClient(api_key="test-key", endpoint_catalog=stub_catalog)

    with pytest.raises(InputValidationError, match="Unknown CoinGlass endpoint_key"):
        client.fetch_endpoint(CoinGlassRequest(endpoint_key="unknown"))

    assert stub_catalog.require_contract_calls == ["unknown"]
    assert stub_catalog.require_url_calls == []


def test_client_metadata_includes_contract_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = EndpointContract(
        key="futures_orderbook_large_limit_order",
        path="/api/futures/orderbook/large-limit-order",
        category="whale_orderbook",
        priority="P1",
        use="current_large_limit_orders_for_whale_orderbook_detection",
        cache_ttl_sec=15,
    )
    stub_catalog = StubCatalog(contract=contract, url="https://stub.coinglass.local/api/futures/orderbook/large-limit-order")

    monkeypatch.setattr(
        "input.input.coinglass.coinglass_client.requests.get",
        lambda *args, **kwargs: DummyResponse(ok=False, status_code=429, payload=None, text="rate limit"),
    )

    client = CoinGlassClient(api_key="test-key", endpoint_catalog=stub_catalog)
    payload = client.fetch_endpoint(
        CoinGlassRequest(endpoint_key=contract.key, symbol="BTC", params={"exchange": "binance"})
    )

    assert payload.status == SourceStatus.ERROR
    assert payload.metadata["path"] == contract.path
    assert payload.metadata["base_url"] == stub_catalog.base_url
    assert payload.metadata["priority"] == contract.priority
    assert payload.metadata["category"] == contract.category
    assert payload.metadata["use"] == contract.use
    assert payload.metadata["cache_ttl_sec"] == contract.cache_ttl_sec
    assert payload.metadata["status_code"] == 429


def test_fetch_raw_converts_source_request_to_coinglass_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, CoinGlassRequest] = {}

    def fake_fetch_endpoint(self: CoinGlassClient, request: CoinGlassRequest) -> RawInputPayload:
        captured["request"] = request
        return RawInputPayload(
            source=self.source_name,
            endpoint=request.endpoint_key,
            status=SourceStatus.OK,
            data={"ok": True},
            metadata={},
        )

    monkeypatch.setattr(CoinGlassClient, "fetch_endpoint", fake_fetch_endpoint)

    client = CoinGlassClient(api_key="test-key")
    response = client.fetch_raw(
        SourceRequest(source="coinglass", endpoint="futures_orderbook_large_limit_order", symbol="BTC", params={"x": 1})
    )

    assert response.status == SourceStatus.OK
    assert captured["request"] == CoinGlassRequest(
        endpoint_key="futures_orderbook_large_limit_order",
        symbol="BTC",
        params={"x": 1},
    )


def test_build_params_preserves_explicit_params_precedence() -> None:
    request = CoinGlassRequest(
        endpoint_key="futures_orderbook_large_limit_order",
        symbol="BTC",
        params={"symbol": "ETH", "interval": "4h", "foo": "bar"},
        exchange="binance",
        interval="1h",
        limit=100,
    )

    params = CoinGlassClient._build_params(request)

    assert params["symbol"] == "ETH"
    assert params["interval"] == "4h"
    assert params["exchange"] == "binance"
    assert params["limit"] == 100
    assert params["foo"] == "bar"
