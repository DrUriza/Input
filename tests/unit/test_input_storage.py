from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from input.processing.raw_response_contracts import RawResponseContract
from input.storage.input_storage import InputStorage


def test_input_storage_persists_run_raw_and_family_vector(tmp_path: Path) -> None:
    database_path = tmp_path / "input_pipeline.sqlite"
    storage = InputStorage(database_path=database_path)
    storage.initialize_database()

    run_id = storage.create_run(
        endpoint_id="coinglass_futures_price_history",
        provider="coinglass",
        family="PRICE_MARKET",
        risk="MEDIUM",
    )

    raw_response = RawResponseContract(
        endpoint_id="coinglass_futures_price_history",
        provider="coinglass",
        url="https://open-api-v4.coinglass.com/api/futures/price/history",
        method="GET",
        status_code=200,
        ok=True,
        params={"symbol": "BTC", "interval": "1h"},
        data={
            "data": [
                {"o": 100000.0, "h": 101000.0, "l": 99500.0, "c": 100500.0, "t": 1710000000},
                {"o": 100500.0, "h": 102000.0, "l": 100200.0, "c": 101700.0, "t": 1710003600},
            ]
        },
        metadata={"source_category": "ohlc", "output_type": "time_series"},
    )
    storage.save_raw_response(run_id=run_id, raw_response=raw_response)

    pipeline_result = SimpleNamespace(
        status="ok",
        family="DERIVATIVES_RISK",
        risk="MEDIUM",
        endpoint_id="coinglass_futures_open_interest",
        provider="coinglass",
        normalized=SimpleNamespace(
            records=(
                {"timestamp": 1710000000, "value": 1.0},
                {"timestamp": 1710003600, "value": 2.0},
            )
        ),
        output_vector=SimpleNamespace(
            features={
                "record_count": 2.0,
                "http_ok": 1.0,
                "access_limited": 0.0,
            },
            metadata={
                "output_type": "time_series",
                "record_count": 2,
                "endpoint_id": "coinglass_futures_open_interest",
            },
        ),
    )
    storage.save_family_vector(run_id=run_id, pipeline_result=pipeline_result)
    storage.complete_run(run_id)

    with sqlite3.connect(database_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        raw_count = connection.execute("SELECT COUNT(*) FROM raw_api_responses").fetchone()[0]
        vector_count = connection.execute("SELECT COUNT(*) FROM family_vectors").fetchone()[0]

    assert run_count == 1
    assert raw_count == 1
    assert vector_count == 1
