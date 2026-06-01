# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - Common
# MODULE NAME:        schemas.py
# DESCRIPTION:        @brief Shared raw payload schemas for input sources
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial raw input dataclasses
# *************************************************************************
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SourceStatus(str, Enum):
    """@brief Minimal provider response status used by the INPUT layer."""

    OK = "ok"
    ERROR = "error"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class SourceRequest:
    """@brief Provider request contract without transport-specific implementation."""

    source: str
    endpoint: str
    symbol: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawInputPayload:
    """@brief Raw or semi-raw response envelope returned by input clients."""

    source: str
    endpoint: str
    status: SourceStatus
    data: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)
