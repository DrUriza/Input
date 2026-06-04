from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...raw_response_contracts import NormalizedResponseContract, RawResponseContract


class CoinGlassNormalizer:
    def normalize(self, raw_response: RawResponseContract) -> NormalizedResponseContract:
        records = self._extract_records(raw_response.data)
        return NormalizedResponseContract(
            endpoint_id=raw_response.endpoint_id,
            provider=raw_response.provider,
            family=str(raw_response.metadata.get("family", "UNCLASSIFIED")),
            output_type=str(raw_response.metadata.get("output_type", "unknown")),
            records=tuple(records),
            metadata={"status_code": raw_response.status_code, **dict(raw_response.metadata)},
        )

    @staticmethod
    def _extract_records(payload: Any) -> list[Mapping[str, Any]]:
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, list):
                return [record for record in data if isinstance(record, Mapping)]
            if isinstance(data, Mapping):
                return [data]
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, Mapping)]
        return [{"value": payload}]
