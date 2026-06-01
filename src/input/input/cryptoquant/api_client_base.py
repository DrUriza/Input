# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - Common
# MODULE NAME:        api_client_base.py
# DESCRIPTION:        @brief Abstract contract for raw external API clients
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial base client interface
# *************************************************************************
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .errors import InputValidationError
from .schemas import RawInputPayload, SourceRequest


class ApiClientBase(ABC):
    """@brief Base class for INPUT clients that fetch raw external data."""

    source_name: str = "unknown"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 20):
        """@brief Store provider configuration without opening network connections."""
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def fetch_raw(self, request: SourceRequest) -> RawInputPayload:
        """@brief Fetch or receive raw provider data for a declared request."""
        raise NotImplementedError

    def validate_minimal_response(self, payload: Any) -> None:
        """@brief Validate that a response object is present before downstream handoff."""
        if payload is None:
            raise InputValidationError(f"{self.source_name} returned an empty payload.")
