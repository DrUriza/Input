from __future__ import annotations

from typing import Mapping

from ..processing.family_vector_contracts import FamilyVectorContract
from ..processing.raw_response_contracts import EndpointMetadata, NormalizedResponseContract


class InputOutputBuilder:
    def build(
        self,
        endpoint: EndpointMetadata,
        normalized: NormalizedResponseContract,
        features: Mapping[str, float],
        risk: str,
    ) -> FamilyVectorContract:
        return FamilyVectorContract(
            endpoint_id=endpoint.endpoint_id,
            provider=endpoint.provider,
            family=endpoint.family or normalized.family,
            risk_class=risk,
            output_type=normalized.output_type,
            features=dict(features),
            normalized_data=normalized.records,
            metadata={
                "output_type": normalized.output_type,
                "record_count": len(normalized.records),
                "endpoint_id": endpoint.endpoint_id,
            },
        )
