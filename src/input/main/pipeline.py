from __future__ import annotations

import json
import os
import time
from dataclasses                             import dataclass
from pathlib                                 import Path
from typing                                  import Any, Mapping
from input.input.coinglass_client            import CoinGlassClient
from input.input.cryptoquant_client          import CryptoQuantClient
from input.processing.raw_response_contracts import EndpointSpecContract, RawResponseContract


DEFAULT_PROVIDER_BASE_URLS = {"coinglass": "https://open-api-v4.coinglass.com", "cryptoquant": "https://api.cryptoquant.com"}
PROVIDER_CLIENTS           = {"coinglass": CoinGlassClient, "cryptoquant": CryptoQuantClient}
DEFAULT_ENDPOINTS_PATH     = Path(__file__).resolve().parents[1] / "config" / "End_Points.json"
DEFAULT_RUNTIME_PATH       = Path(__file__).resolve().parents[1] / "config" / "Run_Time.json"
DEFAULT_RAW_OUTPUT_PATH    = Path(__file__).resolve().parents[1] / "config" / "Raw_End_Points_Response.json"
DEFAULT_SYNTHETIC_RESPONSES_PATH = Path(__file__).resolve().parents[1] / "config" / "Synthetic_End_Point_Responses"


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
    default_params: Mapping[str, Any]
    param_review_required: bool

    @classmethod
    def from_mapping(cls, endpoint_id: str, payload: Mapping[str, Any]) -> "ProviderEndpointRecord":
        required_fields = (
            "endpoint_id",
            "provider",
            "path",
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
            method=str(payload.get("method", "GET")).upper(),
            required_params=tuple(payload["required_params"]),
            optional_params=tuple(payload["optional_params"]),
            family=str(payload["family"]),
            priority=str(payload["priority"]),
            output_type=str(payload["output_type"]),
            ttl_seconds=ttl_seconds,
            default_params=dict(payload.get("default_params", {})),
            param_review_required=bool(payload.get("param_review_required", True)),
        )

    def to_endpoint_spec(self) -> EndpointSpecContract:
        return EndpointSpecContract(
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


class RuntimeControl:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_RUNTIME_PATH

    def read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        for priority in ("P2", "P3"):
            data.setdefault(priority, 0)
        return data

    def is_priority_enabled(self, priority: str) -> bool:
        return int(self.read().get(priority.upper(), 0)) == 1

    def reset_priority(self, priority: str) -> None:
        data = self.read()
        data[priority.upper()] = 0
        data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class EndpointParamResolver:
    _COINGLASS_DEFAULTS: dict[str, Any] = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "limit": 5,
        "exchange": "Binance",
        "exchange_list": "Binance",
        "range": "1",
    }
    _CRYPTOQUANT_DEFAULTS: dict[str, Any] = {
        "exchange": "binance",
        "window": "day",
        "token": "usdt",
        "miner": "all",
        "limit": 5,
        "format": "json",
    }

    @staticmethod
    def _endpoint_defaults(record: ProviderEndpointRecord) -> dict[str, Any]:
        endpoint_id = record.endpoint_id
        defaults: dict[str, Any] = {}

        if record.provider == "coinglass":
            if "aggregated_ask_bids_history" in endpoint_id:
                defaults.update({"exchange_list": "Binance", "symbol": "BTC", "interval": "4h", "limit": 5})
            elif "price_history" in endpoint_id:
                defaults.update({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
            elif "cvd" in endpoint_id or "taker_buy_sell" in endpoint_id:
                defaults.update({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
            elif "orderbook_ask_bids_history" in endpoint_id or "orderbook_pressure" in endpoint_id:
                defaults.update({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
            elif "open_interest" in endpoint_id or "funding_rate" in endpoint_id:
                defaults.update({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
            elif "large_limit_order_history" in endpoint_id:
                defaults.update({"exchange": "Binance", "symbol": "BTCUSDT", "state": 2, "limit": 5})
            elif "large_limit_order" in endpoint_id:
                defaults.update({"exchange": "Binance", "symbol": "BTCUSDT"})
            elif "liquidation" in endpoint_id:
                defaults.update({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})

        if record.provider == "cryptoquant":
            defaults.update({"window": "day", "limit": 5, "format": "json"})
            if "exchange" in record.required_params or "exchange" in endpoint_id:
                defaults["exchange"] = "binance"
            if "token" in record.required_params or "stablecoin" in endpoint_id:
                defaults["token"] = "usdt"
            if "miner" in record.required_params or "miner" in endpoint_id:
                defaults["miner"] = "all"

        return defaults

    @staticmethod
    def _provider_defaults(record: ProviderEndpointRecord) -> dict[str, Any]:
        if record.provider == "coinglass":
            return dict(EndpointParamResolver._COINGLASS_DEFAULTS)
        if record.provider == "cryptoquant":
            return dict(EndpointParamResolver._CRYPTOQUANT_DEFAULTS)
        return {}

    @staticmethod
    def _normalize_params(record: ProviderEndpointRecord, params: dict[str, Any]) -> None:
        if record.provider == "cryptoquant":
            if "exchange" in params:
                params["exchange"] = str(params["exchange"]).lower()
            if "token" in params:
                params["token"] = str(params["token"]).lower()
            params["window"] = "day"
            params["format"] = "json"
            params["limit"] = 5

    def resolve(self, record: ProviderEndpointRecord) -> tuple[dict[str, Any] | None, list[str]]:
        params: dict[str, Any] = dict(record.default_params)
        missing: list[str] = []

        for key, value in self._endpoint_defaults(record).items():
            params.setdefault(key, value)

        provider_defaults = self._provider_defaults(record)
        for field in record.required_params:
            if field not in params and field in provider_defaults:
                params[field] = provider_defaults[field]

        if "limit" in record.optional_params:
            params.setdefault("limit", provider_defaults.get("limit", 5))

        self._normalize_params(record, params)

        for field in record.required_params:
            if field not in params:
                missing.append(field)

        if missing:
            return None, missing

        return params, []


class Pipeline:
    def __init__(
        self,
        endpoints_path: str | Path | None = None,
        runtime_path: str | Path | None = None,
        synthetic_responses_path: str | Path | None = None,
        timeout: int = 20,
        use_synthetic_responses: bool = True,
    ) -> None:
        self.endpoints_path = Path(endpoints_path) if endpoints_path is not None else DEFAULT_ENDPOINTS_PATH
        self.runtime        = RuntimeControl(runtime_path)
        self.param_resolver = EndpointParamResolver()
        self.synthetic_responses_path = (
            Path(synthetic_responses_path) if synthetic_responses_path is not None else DEFAULT_SYNTHETIC_RESPONSES_PATH
        )
        self.use_synthetic_responses = use_synthetic_responses
        self.timeout = timeout
        self.coinglass_client: CoinGlassClient | None = None
        self.cryptoquant_client: CryptoQuantClient | None = None
        self._records = self._load_records(self.endpoints_path)

    @staticmethod
    def _load_dotenv(env_path: Path) -> None:
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)

    def _load_records(self, endpoints_path: Path) -> dict[str, ProviderEndpointRecord]:
        if not endpoints_path.exists():
            raise FileNotFoundError(f"Endpoint registry JSON not found: {endpoints_path}")

        payload = json.loads(endpoints_path.read_text(encoding="utf-8"))
        records: dict[str, ProviderEndpointRecord] = {}

        if isinstance(payload, Mapping) and isinstance(payload.get("priorities"), Mapping):
            for priority_map in payload["priorities"].values():
                if not isinstance(priority_map, Mapping):
                    continue
                for family_entries in priority_map.values():
                    if not isinstance(family_entries, list):
                        continue
                    for entry in family_entries:
                        if not isinstance(entry, Mapping):
                            continue
                        endpoint_id = entry.get("endpoint_id")
                        provider = str(entry.get("provider", ""))
                        if isinstance(endpoint_id, str) and provider in PROVIDER_CLIENTS:
                            records[endpoint_id] = ProviderEndpointRecord.from_mapping(endpoint_id, entry)
            return records

        raise ValueError(f"Unsupported endpoint registry structure in {endpoints_path}")

    def connect(self) -> dict[str, Any]:
        if self.use_synthetic_responses:
            return {
                "mode": "synthetic",
                "synthetic_responses_path": str(self.synthetic_responses_path),
                "coinglass": {"connected": False, "synthetic": True, "error": None},
                "cryptoquant": {"connected": False, "synthetic": True, "error": None},
            }

        project_root = Path(__file__).resolve().parents[3]
        self._load_dotenv(project_root / ".env")

        status: dict[str, Any] = {
            "coinglass": {"connected": False, "error": None},
            "cryptoquant": {"connected": False, "error": None},
        }

        try:
            self.coinglass_client = CoinGlassClient(timeout=self.timeout)
            status["coinglass"] = {"connected": True, **self.coinglass_client.describe_connection()}
        except Exception as exc:
            status["coinglass"]["error"] = str(exc)

        try:
            self.cryptoquant_client = CryptoQuantClient(timeout=self.timeout)
            status["cryptoquant"] = {"connected": True, **self.cryptoquant_client.describe_connection()}
        except Exception as exc:
            status["cryptoquant"]["error"] = str(exc)

        return status

    def endpoint_ids_by_priority(self, priorities: list[str]) -> list[str]:
        priority_set = set(priorities)
        return sorted(endpoint_id for endpoint_id, record in self._records.items() if record.priority in priority_set)

    def get_record(self, endpoint_id: str) -> ProviderEndpointRecord:
        if endpoint_id not in self._records:
            raise KeyError(f"Unknown endpoint_id: {endpoint_id}")
        return self._records[endpoint_id]

    def _client_for(self, provider: str) -> CoinGlassClient | CryptoQuantClient:
        if provider == "coinglass" and self.coinglass_client is not None:
            return self.coinglass_client
        if provider == "cryptoquant" and self.cryptoquant_client is not None:
            return self.cryptoquant_client
        raise RuntimeError(f"Provider '{provider}' is not connected")

    @staticmethod
    def _validate_required_params(record: ProviderEndpointRecord, params: Mapping[str, Any]) -> None:
        missing = [param for param in record.required_params if param not in params]
        if missing:
            raise ValueError(f"Endpoint '{record.endpoint_id}' is missing required params: {missing}")

    def run_raw(self, endpoint_id: str, params: Mapping[str, Any] | None = None) -> RawResponseContract:
        request_params = dict(params or {})
        record = self.get_record(endpoint_id)
        self._validate_required_params(record, request_params)
        if self.use_synthetic_responses:
            return self._fetch_synthetic_raw(record, request_params)
        client = self._client_for(record.provider)
        return client.fetch_raw(record.to_endpoint_spec(), request_params)

    def _fetch_synthetic_raw(self, record: ProviderEndpointRecord, params: Mapping[str, Any]) -> RawResponseContract:
        response_path = self.synthetic_responses_path / f"{record.endpoint_id}.json"
        if not response_path.exists():
            raise FileNotFoundError(f"Synthetic response JSON not found for {record.endpoint_id}: {response_path}")

        data = json.loads(response_path.read_text(encoding="utf-8"))
        text = json.dumps(data, indent=2, default=str)
        return RawResponseContract(
            endpoint_id=record.endpoint_id,
            provider=record.provider,
            url=f"synthetic://{record.provider}/{record.endpoint_id}",
            method=record.method,
            status_code=200,
            ok=True,
            headers={"Content-Type": "application/json", "X-INPUT-Synthetic": "true"},
            text=text,
            data=data,
            params=dict(params),
            metadata={
                "synthetic": True,
                "source_file": str(response_path),
                "ttl_seconds": record.ttl_seconds,
                "priority": record.priority,
                "family": record.family,
                "output_type": record.output_type,
            },
        )

    @staticmethod
    def _raw_response_payload(response: RawResponseContract, record: ProviderEndpointRecord) -> dict[str, Any]:
        payload_status = Pipeline._classify_payload(response)
        return {
            "endpoint_id": response.endpoint_id,
            "provider": response.provider,
            "priority": record.priority,
            "family": record.family,
            "url": response.url,
            "method": response.method,
            "http_status": response.status_code,
            "ok": response.ok,
            "params": dict(response.params),
            "data": response.data,
            "text": response.text,
            "metadata": dict(response.metadata),
            **payload_status,
        }

    @staticmethod
    def _provider_message(data: Any) -> str | None:
        if not isinstance(data, Mapping):
            return None
        for key in ("msg", "message", "description", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        status = data.get("status")
        if isinstance(status, Mapping):
            for key in ("msg", "message", "description", "error"):
                value = status.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _provider_code(data: Any) -> str | int | None:
        if not isinstance(data, Mapping):
            return None
        code = data.get("code")
        if code is not None:
            return code
        status = data.get("status")
        if isinstance(status, Mapping):
            return status.get("code")
        if isinstance(status, (str, int)):
            return status
        return None

    @staticmethod
    def _has_useful_data(data: Any) -> bool:
        if isinstance(data, list):
            return len(data) > 0
        if not isinstance(data, Mapping):
            return data not in (None, "", b"")

        for key in ("data", "result", "results", "items", "list"):
            value = data.get(key)
            if isinstance(value, list) and value:
                return True
            if isinstance(value, Mapping) and value:
                return True

        non_payload_keys = {"code", "msg", "message", "description", "error", "status", "success"}
        return any(key not in non_payload_keys for key in data)

    @staticmethod
    def _classify_payload(response: RawResponseContract) -> dict[str, Any]:
        provider_code = Pipeline._provider_code(response.data)
        provider_message = Pipeline._provider_message(response.data)
        blocked_reason = None
        has_data = Pipeline._has_useful_data(response.data)

        if (
            response.provider == "coinglass"
            and str(provider_code) == "401"
            and provider_message == "Upgrade plan"
        ):
            blocked_reason = "COINGLASS_UPGRADE_PLAN"
            has_data = False
        elif response.provider == "cryptoquant" and response.status_code == 403:
            blocked_reason = "CRYPTOQUANT_FORBIDDEN"
            has_data = False

        return {
            "provider_code": provider_code,
            "provider_message": provider_message,
            "has_data": has_data,
            "blocked_reason": blocked_reason,
        }

    def run_endpoints_by_priority(self, priorities: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        results: list[dict[str, Any]] = []
        raw_responses: list[dict[str, Any]] = []
        endpoint_ids = self.endpoint_ids_by_priority(priorities)

        for endpoint_id in endpoint_ids:
            record = self.get_record(endpoint_id)
            params, missing = self.param_resolver.resolve(record)

            if missing:
                results.append(
                    {
                        "endpoint_id": endpoint_id,
                        "provider": record.provider,
                        "priority": record.priority,
                        "family": record.family,
                        "http_status": None,
                        "ok": False,
                        "skipped": True,
                        "reason": f"missing required_params: {missing}",
                        "params": params or {},
                        "provider_code": None,
                        "provider_message": None,
                        "has_data": False,
                        "blocked_reason": "MISSING_REQUIRED_PARAMS",
                    }
                )
                continue

            try:
                response = self.run_raw(endpoint_id, params)
                payload_status = self._classify_payload(response)
                raw_responses.append(self._raw_response_payload(response, record))
                results.append({"endpoint_id": response.endpoint_id,
                                "provider": response.provider,
                                "priority": record.priority,
                                "family": record.family,
                                "http_status": response.status_code,
                                "ok": response.ok,
                                "params": dict(response.params),
                                **payload_status})
            except Exception as exc:
                results.append({"endpoint_id": endpoint_id,
                                "provider": record.provider,
                                "priority": record.priority,
                                "family": record.family,
                                "error": str(exc),
                                "params": params or {},
                                "provider_code": None,
                                "provider_message": str(exc),
                                "has_data": False,
                                "blocked_reason": "REQUEST_ERROR"})

        return results, raw_responses

    def run_selected_priority_endpoints(
        self,
        priorities: list[str] | None = None,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        selected_priorities = priorities or ["P2", "P3"]
        priority_results: dict[str, list[dict[str, Any]]] = {}
        raw_responses_by_priority: dict[str, list[dict[str, Any]]] = {}

        for priority in selected_priorities:
            priority_key = priority.upper()
            if not self.runtime.is_priority_enabled(priority_key):
                priority_results[priority_key] = [
                    {"priority": priority_key, "executed": False, "message": f"{priority_key} is not enabled"}
                ]
                raw_responses_by_priority[priority_key] = []
                continue

            try:
                results, priority_raw_responses = self.run_endpoints_by_priority([priority_key])
                priority_results[priority_key] = results
                raw_responses_by_priority[priority_key] = priority_raw_responses
            finally:
                self.runtime.reset_priority(priority_key)

        return priority_results, raw_responses_by_priority

    def write_raw_output(
        self,
        connection: Mapping[str, Any],
        results_by_priority: Mapping[str, list[dict[str, Any]]],
        raw_responses_by_priority: Mapping[str, list[dict[str, Any]]],
        output_path: str | Path | None = None,
    ) -> Path:
        target_path = Path(output_path) if output_path is not None else DEFAULT_RAW_OUTPUT_PATH
        priorities = ("P1", "P2", "P3")
        raw_responses = [
            response
            for priority in priorities
            for response in raw_responses_by_priority.get(priority, [])
        ]
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "connection": connection,
            "priorities": {
                priority: {
                    "results": list(results_by_priority.get(priority, [])),
                    "raw_endpoint_responses": list(raw_responses_by_priority.get(priority, [])),
                } for priority in priorities}, "raw_endpoint_responses": raw_responses}
        target_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return target_path

    def run(self) -> dict[str, Any]:
        connection = self.connect()
        p1_results, p1_raw_responses = self.run_endpoints_by_priority(["P1"])
        selected_results, selected_raw_responses = self.run_selected_priority_endpoints()
        results_by_priority = {"P1": p1_results, **selected_results}
        raw_responses_by_priority = {"P1": p1_raw_responses, **selected_raw_responses}
        output_path = self.write_raw_output(connection, results_by_priority, raw_responses_by_priority)
        raw_responses = (list(raw_responses_by_priority.get("P1", [])) + 
                         list(raw_responses_by_priority.get("P2", [])) + 
                         list(raw_responses_by_priority.get("P3", [])))
        result = {"connection": connection,
                  "priorities": results_by_priority,
                  "raw_endpoint_responses": raw_responses,
                  "output_path": str(output_path)}
        print("Done")
        return result


InputPipeline = Pipeline


if __name__ == "__main__":
    Pipeline().run()
