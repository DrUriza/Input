from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..classification.control.family_classifier import FamilyClassifier
from ..classification.control.risk_classifier import RiskClassifier
from ..input.coinglass_client import CoinGlassClient
from ..input.cryptoquant_client import CryptoQuantClient
from ..output.input_output_builder import InputOutputBuilder
from ..processing.math.normalizers.coinglass_normalizer import CoinGlassNormalizer
from ..processing.math.normalizers.cryptoquant_normalizer import CryptoQuantNormalizer
from ..processing.raw_response_contracts import EndpointMetadata, NormalizedResponseContract, RawResponseContract


DEFAULT_PROVIDER_BASE_URLS = {
    "coinglass": "https://open-api-v4.coinglass.com",
    "cryptoquant": "https://api.cryptoquant.com",
}

PROVIDER_CLIENTS = {
    "coinglass": CoinGlassClient,
    "cryptoquant": CryptoQuantClient,
}

DEFAULT_ENDPOINTS_PATH = Path(__file__).resolve().parents[1] / "config" / "End_Points.json"


@dataclass(frozen=True)
class ProviderEndpointRecord:
    endpoint_id: str
    provider: str
    path: str
    method: str
    required_params: tuple[str, ...]
    optional_params: tuple[str, ...]
    family: str
    priority: str
    output_type: str
    ttl_seconds: int

    @classmethod
    def from_mapping(cls, endpoint_id: str, payload: Mapping[str, Any]) -> "ProviderEndpointRecord":
        required_fields = (
            "endpoint_id",
            "provider",
            "path",
            "method",
            "required_params",
            "optional_params",
            "family",
            "priority",
            "output_type",
            "ttl_seconds",
        )
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Endpoint '{endpoint_id}' is missing required fields: {missing}")
        if payload["endpoint_id"] != endpoint_id:
            raise ValueError(f"Endpoint key '{endpoint_id}' does not match endpoint_id '{payload['endpoint_id']}'")

        ttl_seconds = payload["ttl_seconds"]
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 0:
            raise ValueError(f"Endpoint '{endpoint_id}' must define ttl_seconds as a non-negative integer")

        return cls(
            endpoint_id=endpoint_id,
            provider=str(payload["provider"]),
            path=str(payload["path"]),
            method=str(payload["method"]).upper(),
            required_params=tuple(payload["required_params"]),
            optional_params=tuple(payload["optional_params"]),
            family=str(payload["family"]),
            priority=str(payload["priority"]),
            output_type=str(payload["output_type"]),
            ttl_seconds=ttl_seconds,
        )

    def to_endpoint_spec(self) -> EndpointMetadata:
        return EndpointMetadata(
            endpoint_id=self.endpoint_id,
            provider=self.provider,
            path=self.path,
            method=self.method,
            required_params=self.required_params,
            optional_params=self.optional_params,
            family=self.family,
            priority=self.priority,
            output_type=self.output_type,
            ttl_seconds=self.ttl_seconds,
        )


@dataclass(frozen=True)
class PipelineEndpointResult:
    endpoint_id: str
    provider: str
    status: str
    raw_response: RawResponseContract
    normalized: NormalizedResponseContract
    family: str
    risk: str
    output_vector: Any


class Pipeline:
    def __init__(
        self,
        endpoints_path: str | Path | None = None,
        api_keys: Mapping[str, str | None] | None = None,
        base_urls: Mapping[str, str] | None = None,
        timeout: int = 20,
    ) -> None:
        self.endpoints_path = Path(endpoints_path) if endpoints_path is not None else DEFAULT_ENDPOINTS_PATH
        self.api_keys = dict(api_keys or {})
        self.base_urls = {**DEFAULT_PROVIDER_BASE_URLS, **dict(base_urls or {})}
        self.timeout = timeout

        self._records = self._load_records(self.endpoints_path)
        self._clients: dict[str, Any] = {}

        self.family_classifier = FamilyClassifier()
        self.risk_classifier = RiskClassifier()
        self.output_builder = InputOutputBuilder()
        self.normalizers = {"coinglass": CoinGlassNormalizer(), "cryptoquant": CryptoQuantNormalizer()}

    def _load_records(self, endpoints_path: Path) -> dict[str, ProviderEndpointRecord]:
        if not endpoints_path.exists():
            raise FileNotFoundError(f"Endpoint registry JSON not found: {endpoints_path}")

        payload = json.loads(endpoints_path.read_text(encoding="utf-8"))
        records: dict[str, ProviderEndpointRecord] = {}

        # Unified format: priorities -> family -> [endpoint objects]
        if isinstance(payload, Mapping) and isinstance(payload.get("priorities"), Mapping):
            priorities = payload["priorities"]
            for priority_map in priorities.values():
                if not isinstance(priority_map, Mapping):
                    continue
                for family_entries in priority_map.values():
                    if not isinstance(family_entries, list):
                        continue
                    for entry in family_entries:
                        if not isinstance(entry, Mapping):
                            continue
                        endpoint_id = entry.get("endpoint_id")
                        if not isinstance(endpoint_id, str):
                            continue
                        provider = str(entry.get("provider", ""))
                        if provider not in PROVIDER_CLIENTS:
                            continue
                        record = ProviderEndpointRecord.from_mapping(endpoint_id, entry)
                        records[endpoint_id] = record
            return records

        # Flat format: endpoint_id -> endpoint object
        if isinstance(payload, Mapping):
            for endpoint_id, entry in payload.items():
                if not isinstance(endpoint_id, str) or not isinstance(entry, Mapping):
                    continue
                provider = str(entry.get("provider", ""))
                if provider not in PROVIDER_CLIENTS:
                    continue
                records[endpoint_id] = ProviderEndpointRecord.from_mapping(endpoint_id, entry)
            return records

        raise ValueError(f"Unsupported endpoint registry structure in {endpoints_path}")

    def list_endpoint_ids(self) -> list[str]:
        return sorted(self._records)

    def _require_record(self, endpoint_id: str) -> ProviderEndpointRecord:
        if endpoint_id not in self._records:
            raise KeyError(f"Unknown endpoint_id: {endpoint_id}")
        return self._records[endpoint_id]

    @staticmethod
    def _validate_required_params(record: ProviderEndpointRecord, params: Mapping[str, Any]) -> None:
        missing = [param for param in record.required_params if param not in params]
        if missing:
            raise ValueError(f"Endpoint '{record.endpoint_id}' is missing required params: {missing}")

    def _client_for(self, provider: str):
        if provider not in PROVIDER_CLIENTS:
            raise ValueError(f"Unsupported provider: {provider}")
        if provider not in self._clients:
            client_cls = PROVIDER_CLIENTS[provider]
            api_key = self.api_keys.get(provider)
            self._clients[provider] = client_cls(
                base_url=self.base_urls[provider],
                api_key=api_key,
                timeout=self.timeout,
            )
        return self._clients[provider]

    def run(self, endpoint_id: str, params: Mapping[str, Any] | None = None) -> RawResponseContract:
        request_params = dict(params or {})
        record = self._require_record(endpoint_id)
        self._validate_required_params(record, request_params)
        client = self._client_for(record.provider)
        return client.fetch_raw(record.to_endpoint_spec(), request_params)

    @staticmethod
    def _response_message(response: RawResponseContract) -> str:
        if isinstance(response.data, Mapping):
            for key in ("msg", "message", "description"):
                value = response.data.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            status = response.data.get("status")
            if isinstance(status, Mapping):
                for key in ("message", "description"):
                    value = status.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
        return response.text or ""

    @staticmethod
    def _has_provider_access_error(response: RawResponseContract) -> bool:
        body_code = None
        if isinstance(response.data, Mapping):
            body_code = response.data.get("code")

        if response.status_code in (401, 403):
            return True

        if isinstance(body_code, str) and body_code in {"401", "403"}:
            return True
        if isinstance(body_code, int) and body_code in {401, 403}:
            return True

        message = Pipeline._response_message(response).lower()
        keywords = (
            "upgrade plan",
            "subscription",
            "unauthorized",
            "invalid api key",
            "forbidden",
            "token does not exists",
            "permission",
        )
        return any(keyword in message for keyword in keywords)

    @staticmethod
    def _resolve_endpoint_metadata(record: Any) -> EndpointMetadata:
        if hasattr(record, "to_endpoint_spec"):
            return record.to_endpoint_spec()
        if isinstance(record, EndpointMetadata):
            return record
        raise TypeError("Unsupported endpoint registry record type")

    def _normalize(self, response: RawResponseContract) -> NormalizedResponseContract:
        normalizer = self.normalizers.get(response.provider)
        if normalizer is None:
            return NormalizedResponseContract(
                endpoint_id=response.endpoint_id,
                provider=response.provider,
                family=str(response.metadata.get("family", "UNCLASSIFIED")),
                output_type=str(response.metadata.get("output_type", "unknown")),
                records=tuple(),
                metadata={"status_code": response.status_code, **dict(response.metadata)},
            )
        return normalizer.normalize(response)

    def run_endpoint(self, endpoint_id: str, params: Mapping[str, Any] | None = None) -> PipelineEndpointResult:
        record = self._require_record(endpoint_id)
        endpoint = self._resolve_endpoint_metadata(record)
        raw_response = self.run(endpoint_id=endpoint_id, params=params)

        provider_access_limited = self._has_provider_access_error(raw_response)
        status = "ok"
        if provider_access_limited:
            status = "provider_access_limited"
        elif not raw_response.ok:
            status = "provider_error"

        normalized = self._normalize(raw_response)
        family = self.family_classifier.classify(endpoint, normalized)
        risk = self.risk_classifier.classify(endpoint, normalized)

        features = {
            "record_count": float(len(normalized.records)),
            "http_ok": 1.0 if raw_response.ok else 0.0,
            "access_limited": 1.0 if provider_access_limited else 0.0,
        }
        vector = self.output_builder.build(endpoint=endpoint, normalized=normalized, features=features, risk=risk)

        return PipelineEndpointResult(
            endpoint_id=endpoint_id,
            provider=raw_response.provider,
            status=status,
            raw_response=raw_response,
            normalized=normalized,
            family=family,
            risk=risk,
            output_vector=vector,
        )

    def run_batch(self, calls: Sequence[tuple[str, Mapping[str, Any]]]) -> list[PipelineEndpointResult]:
        results: list[PipelineEndpointResult] = []
        for endpoint_id, params in calls:
            results.append(self.run_endpoint(endpoint_id=endpoint_id, params=params))
        return results


InputPipeline = Pipeline
