# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - CoinGlass
# MODULE NAME:        coinglass_client.py
# DESCRIPTION:        @brief Client for raw CoinGlass derivatives market data
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial CoinGlass client contract without API implementation
#                     09.05.2026 - Implemented CoinGlass V4 raw derivatives fetch
#                     09.05.2026 - Added Doxygen comments and endpoint catalog injection
# *************************************************************************
from __future__ import annotations

import os
from typing import Any

import requests

from project_trading.input.common.api_client_base import ApiClientBase
from project_trading.input.common.errors import InputProviderError, InputValidationError
from project_trading.input.common.schemas import RawInputPayload, SourceRequest, SourceStatus

from .coinglass_endpoints import COINGLASS_BASE_URL, CoinGlassEndpointCatalog
from .coinglass_models import CoinGlassRequest


# /// ***********************************************************************************************************************
# /// Classname:          CoinGlassClient(ApiClientBase)
# ///
# /// @brief              HTTP client for CoinGlass raw derivatives input data
# /// @pre                requests package must be available and the caller must provide a valid request object
# /// @post               The client is configured for raw CoinGlass transport and endpoint catalog lookup
# /// @param[in]          ApiClientBase: Common INPUT API client base class
# /// @return             CoinGlassClient class definition
# /// @InOutCorrelation
# /// The client owns provider transport configuration and a CoinGlassEndpointCatalog instance. Incoming source
# /// requests are converted to CoinGlassRequest objects, endpoint keys are resolved through the catalog, and
# /// successful provider responses are wrapped as RawInputPayload without feature normalization or trading logic.
# /// @callsequence       @startuml
# ///                     start
# ///                       :Receive raw INPUT request;
# ///                       :Resolve endpoint key through CoinGlassEndpointCatalog;
# ///                       if (API key available?) then (yes)
# ///                         :Build query params;
# ///                         :Execute HTTP GET against CoinGlass V4;
# ///                         if (HTTP response OK?) then (yes)
# ///                           :Parse complete provider JSON;
# ///                           :Return RawInputPayload with SourceStatus.OK;
# ///                         else (no)
# ///                           :Return RawInputPayload with SourceStatus.ERROR;
# ///                         endif
# ///                       else (no)
# ///                         :Raise InputProviderError;
# ///                       endif
# ///                     end
# ///                     @enduml
# /// @traceability
# /// ***********************************************************************************************************************
class CoinGlassClient(ApiClientBase):

    source_name = "coinglass"

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassClient.__init__(api_key: str | None = None,
    # ///                     base_url: str | None = None,
    # ///                     timeout: int = 20,
    # ///                     endpoint_catalog: CoinGlassEndpointCatalog | None = None)
    # ///
    # /// @brief              Configure CoinGlass transport using explicit values or environment variables
    # /// @pre                base_url, when provided, must be a CoinGlass-compatible API root URL
    # /// @post               api_key, base_url, timeout and endpoint_catalog are stored in the client instance
    # /// @param[in]          api_key: Optional CoinGlass API key; falls back to COINGLASS_API_KEY
    # /// @param[in]          base_url: Optional CoinGlass base URL; falls back to COINGLASS_BASE_URL
    # /// @param[in]          timeout: HTTP request timeout in seconds
    # /// @param[in]          endpoint_catalog: Optional endpoint catalog for dependency injection
    # /// @return             None
    # /// @InOutCorrelation
    # /// The constructor resolves runtime configuration in one place. Explicit constructor arguments take precedence
    # /// over environment variables, and the endpoint catalog defaults to the production CoinGlass derivatives MVP
    # /// catalog when no test or custom catalog is injected.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Read explicit api_key/base_url arguments;
    # ///                       :Fallback to environment variables;
    # ///                       :Fallback to COINGLASS_BASE_URL constant;
    # ///                       :Initialize ApiClientBase fields;
    # ///                       if (endpoint_catalog provided?) then (yes)
    # ///                         :Use injected catalog;
    # ///                       else (no)
    # ///                         :Create default CoinGlassEndpointCatalog;
    # ///                       endif
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str | None = None,
                 timeout: int = 20,
                 endpoint_catalog: CoinGlassEndpointCatalog | None = None):
        resolved_api_key = api_key or os.getenv("COINGLASS_API_KEY")
        resolved_base_url = base_url or os.getenv("COINGLASS_BASE_URL") or COINGLASS_BASE_URL
        super().__init__(api_key=resolved_api_key, base_url=resolved_base_url.rstrip("/"), timeout=timeout)
        self.endpoint_catalog = endpoint_catalog or CoinGlassEndpointCatalog()

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassClient.fetch_raw(request: SourceRequest)
    # ///
    # /// @brief              Fetch raw CoinGlass data from a generic INPUT source request
    # /// @pre                request must target source "coinglass" or leave source empty-compatible
    # /// @post               The generic request is converted and delegated to fetch_endpoint
    # /// @param[in]          request: Generic INPUT source request
    # /// @return             RawInputPayload containing provider JSON or transport error metadata
    # /// @InOutCorrelation
    # /// The method preserves the common SourceRequest contract while routing through the CoinGlass-specific request
    # /// object. It validates provider ownership only, then delegates all endpoint resolution, credential validation,
    # /// HTTP execution and payload wrapping to fetch_endpoint.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Receive SourceRequest;
    # ///                       if (source is coinglass-compatible?) then (yes)
    # ///                         :Create CoinGlassRequest from endpoint/symbol/params;
    # ///                         :Call fetch_endpoint;
    # ///                         :Return RawInputPayload;
    # ///                       else (no)
    # ///                         :Raise InputValidationError;
    # ///                       endif
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    def fetch_raw(self, request: SourceRequest) -> RawInputPayload:
        if request.source and request.source != self.source_name:
            raise InputValidationError(f"Invalid source for CoinGlass client: {request.source}")

        coinglass_request = CoinGlassRequest(
            endpoint_key=request.endpoint,
            symbol=request.symbol,
            params=request.params,
        )
        return self.fetch_endpoint(coinglass_request)

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassClient.fetch_endpoint(request: CoinGlassRequest)
    # ///
    # /// @brief              Fetch a named CoinGlass endpoint without downstream interpretation
    # /// @pre                request.endpoint_key must exist in CoinGlassEndpointCatalog and COINGLASS_API_KEY must exist
    # /// @post               The returned RawInputPayload contains the complete provider JSON or error metadata
    # /// @param[in]          request: CoinGlass-specific raw request contract
    # /// @return             RawInputPayload with source, endpoint, status, raw data and metadata
    # /// @InOutCorrelation
    # /// Endpoint lookup, API-key validation, HTTP transport and response wrapping happen in this method. Provider JSON
    # /// is kept intact in payload.data. Failed HTTP responses are not hidden; status_code and response_text are placed
    # /// in metadata while the payload status is set to SourceStatus.ERROR.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Resolve endpoint path from catalog;
    # ///                       if (endpoint exists?) then (yes)
    # ///                         if (api key exists?) then (yes)
    # ///                           :Build request params;
    # ///                           :Create URL and CoinGlass headers;
    # ///                           :Execute requests.get;
    # ///                           :Build metadata;
    # ///                           if (response.ok) then (yes)
    # ///                             :Parse JSON body;
    # ///                             :Validate response is present;
    # ///                             :Return OK RawInputPayload;
    # ///                           else (no)
    # ///                             :Attach response text;
    # ///                             :Return ERROR RawInputPayload;
    # ///                           endif
    # ///                         else (no)
    # ///                           :Raise InputProviderError;
    # ///                         endif
    # ///                       else (no)
    # ///                         :Raise InputValidationError;
    # ///                       endif
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    def fetch_endpoint(self, request: CoinGlassRequest) -> RawInputPayload:
        endpoint_path = self.endpoint_catalog.get_path(request.endpoint_key)
        if endpoint_path is None:
            raise InputValidationError(f"Unknown CoinGlass endpoint_key: {request.endpoint_key}")

        if not self.api_key:
            raise InputProviderError("Missing COINGLASS_API_KEY")

        params = self._build_params(request)
        url = f"{self.base_url}{endpoint_path}"
        headers = {"CG-API-KEY": self.api_key, "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise InputProviderError(f"CoinGlass request failed for {request.endpoint_key}: {exc}") from exc

        metadata: dict[str, Any] = {
            "symbol": request.symbol,
            "params": params,
            "path": endpoint_path,
            "base_url": self.base_url,
            "status_code": response.status_code,
        }

        if not response.ok:
            metadata["response_text"] = response.text
            return RawInputPayload(
                source=self.source_name,
                endpoint=request.endpoint_key,
                status=SourceStatus.ERROR,
                data=None,
                metadata=metadata,
            )

        try:
            data = response.json()
        except ValueError as exc:
            metadata["response_text"] = response.text
            raise InputProviderError(f"CoinGlass returned non-JSON response for {request.endpoint_key}") from exc

        self.validate_minimal_response(data)
        return RawInputPayload(
            source=self.source_name,
            endpoint=request.endpoint_key,
            status=SourceStatus.OK,
            data=data,
            metadata=metadata,
        )

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassClient._build_params(request: CoinGlassRequest)
    # ///
    # /// @brief              Merge explicit request fields into query params without feature normalization
    # /// @pre                request must be a CoinGlassRequest instance
    # /// @post               Returned params include optional symbol, exchange, interval and limit when provided
    # /// @param[in]          request: CoinGlass-specific raw request contract
    # /// @return             dict[str, Any] query parameters sent to CoinGlass
    # /// @InOutCorrelation
    # /// Existing request.params values take precedence. Optional convenience fields are added only when the caller did
    # /// not already provide the same key, preserving caller intent and avoiding hidden normalization.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Copy request.params;
    # ///                       if (symbol provided and absent in params) then (yes)
    # ///                         :Set symbol;
    # ///                       endif
    # ///                       if (exchange provided and absent in params) then (yes)
    # ///                         :Set exchange;
    # ///                       endif
    # ///                       if (interval provided and absent in params) then (yes)
    # ///                         :Set interval;
    # ///                       endif
    # ///                       if (limit provided and absent in params) then (yes)
    # ///                         :Set limit;
    # ///                       endif
    # ///                       :Return params;
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    @staticmethod
    def _build_params(request: CoinGlassRequest) -> dict[str, Any]:
        params = dict(request.params or {})
        if request.symbol is not None:
            params.setdefault("symbol", request.symbol)
        if request.exchange is not None:
            params.setdefault("exchange", request.exchange)
        if request.interval is not None:
            params.setdefault("interval", request.interval)
        if request.limit is not None:
            params.setdefault("limit", request.limit)
        return params
