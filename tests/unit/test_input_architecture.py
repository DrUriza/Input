from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from input.classification.control.family_classifier import FamilyClassifier
from input.classification.control.risk_classifier import RiskClassifier
from input.processing.raw_response_contracts import EndpointMetadata, RawResponseContract
from input.main.pipeline import Pipeline
from input.output.input_output_builder import InputOutputBuilder
from input.processing.math.normalizers.coinglass_normalizer import CoinGlassNormalizer
from input.processing.math.feature_math import moving_average, percent_change, safe_divide, z_score


class StubClient:
    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self.calls: list[tuple[EndpointMetadata, dict[str, Any]]] = []

    def fetch_raw(self, endpoint: EndpointMetadata, params: dict[str, Any]) -> RawResponseContract:
        self.calls.append((endpoint, params))
        return RawResponseContract(
            endpoint_id=endpoint.endpoint_id,
            provider=endpoint.provider,
            url=f"https://stub/{endpoint.endpoint_id}",
            method=endpoint.method,
            status_code=200,
            ok=True,
            data={"data": [{"value": 2.0}, {"value": 4.0}]},
            params=params,
            metadata={"family": endpoint.family, "output_type": endpoint.output_type},
        )


def write_registry(tmp_path: Path, provider: str, endpoint_id: str, path: str, required_params: list[str]) -> Path:
    registry_path = tmp_path / "End_Points.json"
    registry_path.write_text(
        json.dumps(
            {
                "priorities": {
                    "P1": {
                        "DERIVATIVES_RISK": [
                            {
                                "endpoint_id": endpoint_id,
                                "provider": provider,
                                "path": path,
                                "method": "GET",
                                "required_params": required_params,
                                "optional_params": ["limit"],
                                "family": "DERIVATIVES_RISK",
                                "priority": "P1",
                                "output_type": "time_series",
                                "ttl_seconds": 60,
                            }
                        ]
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return registry_path


def test_endpoint_runner_routes_by_provider(tmp_path: Path) -> None:
    coinglass_registry = write_registry(
        tmp_path,
        provider="coinglass",
        endpoint_id="coinglass_futures_open_interest_history",
        path="/api/futures/open-interest/history",
        required_params=["symbol", "interval"],
    )
    coinglass_client = StubClient("coinglass")
    pipeline = Pipeline(endpoints_path=coinglass_registry)
    pipeline._clients["coinglass"] = coinglass_client

    response = pipeline.run(
        "coinglass_futures_open_interest_history",
        params={"symbol": "BTC", "interval": "1h"},
    )

    assert response.ok is True
    assert coinglass_client.calls
    assert response.endpoint_id == "coinglass_futures_open_interest_history"


def test_normalization_classification_and_output_vector() -> None:
    endpoint = EndpointMetadata(
        endpoint_id="coinglass_futures_open_interest_history",
        provider="coinglass",
        path="/api/futures/open-interest/history",
        method="GET",
        required_params=("symbol", "interval"),
        family="DERIVATIVES_RISK",
        priority="P1",
        output_type="time_series",
        ttl_seconds=60,
    )
    raw = RawResponseContract(
        endpoint_id=endpoint.endpoint_id,
        provider=endpoint.provider,
        url="https://stub/coinglass_futures_open_interest_history",
        method=endpoint.method,
        status_code=200,
        ok=True,
        data={"data": [{"value": 1.0}, {"value": 3.0}]},
        params={"symbol": "BTC", "interval": "1h"},
        metadata={"family": endpoint.family, "output_type": endpoint.output_type},
    )

    normalized = CoinGlassNormalizer().normalize(raw)
    family = FamilyClassifier().classify(endpoint, normalized)
    risk = RiskClassifier().classify(endpoint, normalized)
    features = {
        "mean_value": moving_average([1.0, 3.0]),
        "delta": percent_change(3.0, 1.0),
        "ratio": safe_divide(3.0, 1.0),
        "z_score": z_score(3.0, [1.0, 3.0]),
    }
    vector = InputOutputBuilder().build(endpoint, normalized, features, risk)

    assert len(normalized.records) == 2
    assert family == "DERIVATIVES_RISK"
    assert risk == "MEDIUM"
    assert vector.family == "DERIVATIVES_RISK"
    assert vector.risk_class == "MEDIUM"
    assert vector.output_type == "time_series"
