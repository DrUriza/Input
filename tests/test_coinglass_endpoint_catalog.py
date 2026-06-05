from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from input.main.pipeline import Pipeline
from input.processing.raw_response_contracts import EndpointMetadata, RawResponseContract


ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS_PATH = ROOT / "src" / "input" / "config" / "End_Points.json"


def _load_registry_payload() -> dict[str, Any]:
    return json.loads(ENDPOINTS_PATH.read_text(encoding="utf-8"))


def _iter_endpoint_entries(payload: dict[str, Any]):
    for priority in payload.get("priorities", {}).values():
        if not isinstance(priority, dict):
            continue
        for family_entries in priority.values():
            if not isinstance(family_entries, list):
                continue
            for entry in family_entries:
                if isinstance(entry, dict):
                    yield entry


def _params_for(required_params: tuple[str, ...]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "exchange": "Binance",
        "limit": 1,
        "start_time": 0,
        "end_time": 0,
    }
    return {param: defaults.get(param, "BTC") for param in required_params}


class StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[EndpointMetadata, dict[str, Any]]] = []

    def fetch_raw(self, endpoint: EndpointMetadata, params: dict[str, Any] | None = None) -> RawResponseContract:
        request_params = dict(params or {})
        self.calls.append((endpoint, request_params))
        return RawResponseContract(
            endpoint_id=endpoint.endpoint_id,
            provider=endpoint.provider,
            url=f"https://stub.local{endpoint.path}",
            method=endpoint.method,
            status_code=200,
            ok=True,
            data={"data": [{"value": 1.0}]},
            params=request_params,
            metadata={"family": endpoint.family, "output_type": endpoint.output_type},
        )


def test_registry_json_exists_and_has_priorities() -> None:
    payload = _load_registry_payload()
    assert ENDPOINTS_PATH.exists()
    assert "priorities" in payload
    assert set(payload["priorities"].keys()) >= {"P1", "P2", "P3"}


def test_registry_disallows_direct_binance_provider() -> None:
    payload = _load_registry_payload()
    entries = list(_iter_endpoint_entries(payload))
    providers = {str(entry.get("provider", "")).lower() for entry in entries}

    assert "binance" in {p.lower() for p in payload.get("forbidden_direct_providers", [])}
    assert "binance" not in providers


def test_no_binance_client_module_or_file() -> None:
    binance_client_path = ROOT / "src" / "input" / "input" / "binance_client.py"
    assert not binance_client_path.exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("input.input.binance_client")


def test_pipeline_loads_registry_without_legacy_catalog() -> None:
    pipeline = Pipeline(endpoints_path=ENDPOINTS_PATH)
    endpoint_ids = pipeline.list_endpoint_ids()

    assert endpoint_ids
    assert any(endpoint_id.startswith("coinglass_") for endpoint_id in endpoint_ids)


def test_pipeline_resolves_endpoints_from_registry_not_hardcoded_paths() -> None:
    pipeline = Pipeline(endpoints_path=ENDPOINTS_PATH)
    endpoint_id = next(
        candidate
        for candidate in pipeline.list_endpoint_ids()
        if pipeline._records[candidate].provider == "coinglass"
    )
    record = pipeline._records[endpoint_id]

    stub_client = StubClient()
    pipeline._clients["coinglass"] = stub_client

    response = pipeline.run(endpoint_id=endpoint_id, params=_params_for(record.required_params))

    assert stub_client.calls
    called_endpoint, _ = stub_client.calls[0]
    assert called_endpoint.path == record.path
    assert called_endpoint.endpoint_id == endpoint_id
    assert response.url.endswith(record.path)
