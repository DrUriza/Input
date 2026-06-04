from __future__ import annotations

from ...processing.raw_response_contracts import EndpointMetadata, NormalizedResponseContract

class FamilyClassifier:
    def classify(self, endpoint: EndpointMetadata, normalized: NormalizedResponseContract) -> str:
        if endpoint.family:
            return endpoint.family
        if normalized.family:
            return normalized.family
        return "UNCLASSIFIED"
    