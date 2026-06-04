from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class FamilyVectorContract:
    endpoint_id: str
    provider: str
    family: str
    risk_class: str
    output_type: str
    features: Mapping[str, float] = field(default_factory=dict)
    normalized_data: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
