from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from input.main.pipeline import Pipeline
from input.processing.raw_response_contracts import EndpointMetadata, RawResponseContract


class StubRecord:
    def __init__(self, endpoint: EndpointMetadata) -> None:
        self._endpoint = endpoint
        self.endpoint_id = endpoint.endpoint_id
        self.provider = endpoint.provider
        self.path = endpoint.path
        self.method = endpoint.method
        self.required_params = endpoint.required_params
        self.optional_params = endpoint.optional_params
        self.family = endpoint.family
        self.priority = endpoint.priority
        self.output_type = endpoint.output_type
        self.ttl_seconds = endpoint.ttl_seconds

    def to_endpoint_spec(self) -> EndpointMetadata:
        return self._endpoint


class StubClient:
    def __init__(self, response: RawResponseContract) -> None:
        self.response = response

    def fetch_raw(self, endpoint: EndpointMetadata, params=None) -> RawResponseContract:
        return self.response


def test_pipeline_marks_plan_error_as_access_limited_and_returns_vector() -> None:
    endpoint = EndpointMetadata(
        endpoint_id="coinglass_futures_open_interest",
        provider="coinglass",
        path="/api/futures/open-interest/history",
        method="GET",
        required_params=("symbol", "interval"),
        family="DERIVATIVES_RISK",
        priority="P1",
        output_type="time_series",
        ttl_seconds=60,
    )
    response = RawResponseContract(
        endpoint_id=endpoint.endpoint_id,
        provider=endpoint.provider,
        url="https://open-api-v4.coinglass.com/api/futures/open-interest/history",
        method="GET",
        status_code=200,
        ok=True,
        data={"code": "401", "msg": "Upgrade plan"},
        params={"symbol": "BTC", "interval": "1h"},
        metadata={"family": endpoint.family, "output_type": endpoint.output_type},
        text=json.dumps({"code": "401", "msg": "Upgrade plan"}),
    )

    pipeline = Pipeline(endpoints_path=Path("src/input/config/End_Points.json"))
    pipeline._records = {endpoint.endpoint_id: StubRecord(endpoint)}
    pipeline._clients[endpoint.provider] = StubClient(response)
    result = pipeline.run_endpoint(endpoint_id=endpoint.endpoint_id, params={"symbol": "BTC", "interval": "1h"})

    assert result.status == "provider_access_limited"
    assert result.output_vector.risk_class == "MEDIUM"
    assert result.output_vector.features["access_limited"] == 1.0


def test_pipeline_keeps_success_path() -> None:
    endpoint = EndpointMetadata(
        endpoint_id="coinglass_futures_open_interest",
        provider="coinglass",
        path="/api/futures/open-interest/history",
        method="GET",
        required_params=("symbol", "interval"),
        family="DERIVATIVES_RISK",
        priority="P1",
        output_type="time_series",
        ttl_seconds=60,
    )
    response = RawResponseContract(
        endpoint_id=endpoint.endpoint_id,
        provider=endpoint.provider,
        url="https://open-api-v4.coinglass.com/api/futures/open-interest/history",
        method="GET",
        status_code=200,
        ok=True,
        data={"data": [{"value": 1.0}, {"value": 2.0}]},
        params={"symbol": "BTC", "interval": "1h"},
        metadata={"family": endpoint.family, "output_type": endpoint.output_type},
        text="",
    )

    pipeline = Pipeline(endpoints_path=Path("src/input/config/End_Points.json"))
    pipeline._records = {endpoint.endpoint_id: StubRecord(endpoint)}
    pipeline._clients[endpoint.provider] = StubClient(response)
    result = pipeline.run_endpoint(endpoint_id=endpoint.endpoint_id, params={"symbol": "BTC", "interval": "1h"})

    assert result.status == "ok"
    assert result.family == "DERIVATIVES_RISK"
    assert result.output_vector.features["record_count"] == 2.0
