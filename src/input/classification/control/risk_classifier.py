from __future__ import annotations

from ...processing.raw_response_contracts import EndpointMetadata, NormalizedResponseContract


class RiskClassifier:
    def classify(self, endpoint: EndpointMetadata, normalized: NormalizedResponseContract) -> str:
        if endpoint.output_type != "time_series":
            return "LOW"
        if endpoint.ttl_seconds <= 30:
            return "HIGH"
        if endpoint.ttl_seconds <= 300:
            return "MEDIUM"
        return "LOW"