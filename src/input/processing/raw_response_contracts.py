from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EndpointMetadata:
    endpoint_id: str
    provider: str
    path: str
    method: str = "GET"
    required_params: tuple[str, ...] = field(default_factory=tuple)
    optional_params: tuple[str, ...] = field(default_factory=tuple)
    family: str = "UNCLASSIFIED"
    priority: str = "P3"
    output_type: str = "time_series"
    ttl_seconds: int = 0


@dataclass(frozen=True)
class RawResponseContract:
    endpoint_id: str
    provider: str
    url: str
    method: str
    status_code: int | None
    ok: bool
    headers: Mapping[str, str] = field(default_factory=dict)
    text: str = ""
    data: Any = None
    params: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


EndpointSpecContract = EndpointMetadata


@dataclass(frozen=True)
class NormalizedResponseContract:
    endpoint_id: str
    provider: str
    family: str
    output_type: str
    records: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
