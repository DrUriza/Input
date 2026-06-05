from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class InputStorage:
    def __init__(self, database_path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parent / "input_pipeline.sqlite"
        self.database_path = Path(database_path) if database_path is not None else default_path

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        if self.database_path != Path(":memory:"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_json(value: Any) -> str:
        if value is None:
            return "{}"
        if isinstance(value, str):
            return value

        def default_serializer(obj: Any) -> Any:
            if is_dataclass(obj):
                return asdict(obj)
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        return json.dumps(value, ensure_ascii=False, default=default_serializer)

    @staticmethod
    def _get_field(payload: Any, field_name: str, default: Any = None) -> Any:
        if payload is None:
            return default
        if isinstance(payload, Mapping):
            return payload.get(field_name, default)
        return getattr(payload, field_name, default)

    @staticmethod
    def _ensure_mapping(value: Any) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        return {}

    def initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    endpoint_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    family TEXT,
                    risk TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_api_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    status_code INTEGER,
                    ok INTEGER NOT NULL,
                    params_json TEXT NOT NULL,
                    raw_data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS family_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    family TEXT,
                    risk TEXT,
                    status TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    features_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    quality_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
                )
                """
            )

    def create_run(self, endpoint_id: str, provider: str, family: str | None = None, risk: str | None = None) -> str:
        run_id = str(uuid4())
        started_at = self._utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs (run_id, endpoint_id, provider, family, risk, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, endpoint_id, provider, family, risk, "running", started_at),
            )

        return run_id

    def save_raw_response(self, run_id: str, raw_response: Any) -> None:
        endpoint_id = self._get_field(raw_response, "endpoint_id")
        provider = self._get_field(raw_response, "provider")
        status_code = self._get_field(raw_response, "status_code")
        ok = self._get_field(raw_response, "ok", False)
        params = self._get_field(raw_response, "params", {})
        raw_data = self._get_field(raw_response, "data", {})

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO raw_api_responses (
                    run_id,
                    endpoint_id,
                    provider,
                    status_code,
                    ok,
                    params_json,
                    raw_data_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    endpoint_id,
                    provider,
                    status_code,
                    1 if bool(ok) else 0,
                    self._to_json(params),
                    self._to_json(raw_data),
                    self._utc_now(),
                ),
            )

    def save_family_vector(self, run_id: str, pipeline_result: Any) -> None:
        endpoint_id = self._get_field(pipeline_result, "endpoint_id")
        provider = self._get_field(pipeline_result, "provider")
        family = self._get_field(pipeline_result, "family")
        risk = self._get_field(pipeline_result, "risk")
        status = self._get_field(pipeline_result, "status", "unknown")

        normalized = self._get_field(pipeline_result, "normalized")
        normalized_records = self._get_field(normalized, "records", ())
        output_vector = self._get_field(pipeline_result, "output_vector")
        features = self._get_field(output_vector, "features", {})
        metadata = self._get_field(output_vector, "metadata", {})
        quality = self._get_field(output_vector, "quality", {})

        if not metadata:
            metadata = self._ensure_mapping(self._get_field(pipeline_result, "metadata", {}))

        record_count = int(self._get_field(pipeline_result, "record_count", len(normalized_records)))

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO family_vectors (
                    run_id,
                    endpoint_id,
                    provider,
                    family,
                    risk,
                    status,
                    record_count,
                    features_json,
                    metadata_json,
                    quality_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    endpoint_id,
                    provider,
                    family,
                    risk,
                    status,
                    record_count,
                    self._to_json(features),
                    self._to_json(metadata),
                    self._to_json(quality if isinstance(quality, Mapping) else {}),
                    self._utc_now(),
                ),
            )

    def complete_run(self, run_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE pipeline_runs
                SET status = ?, completed_at = ?
                WHERE run_id = ?
                """,
                ("completed", self._utc_now(), run_id),
            )

    def fail_run(self, run_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE pipeline_runs
                SET status = ?, completed_at = ?, error = ?
                WHERE run_id = ?
                """,
                ("failed", self._utc_now(), error, run_id),
            )
