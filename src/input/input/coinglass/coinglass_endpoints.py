# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - CoinGlass
# MODULE NAME:        coinglass_endpoints.py
# DESCRIPTION:        @brief CoinGlass V4 derivatives endpoint catalog
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial endpoint catalog without request logic
#                     09.05.2026 - Added CoinGlass V4 derivatives MVP endpoints
#                     09.05.2026 - Added endpoint catalog object for OO access
# *************************************************************************
from __future__  import annotations
from dataclasses import dataclass, field
from typing      import Mapping

COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com"

COINGLASS_ENDPOINTS = {
    "open_interest_ohlc": "/api/futures/openInterest/ohlc-history",
    "open_interest_aggregated": "/api/futures/openInterest/aggregated-history",
    "funding_rate_ohlc": "/api/futures/fundingRate/ohlc-history",
    "funding_rate_oi_weighted": "/api/futures/fundingRate/oi-weight-ohlc-history",
    "liquidation_history": "/api/futures/liquidation/history",
    "liquidation_aggregated": "/api/futures/liquidation/aggregated-history",
    "global_long_short_ratio": "/api/futures/global-long-short-account-ratio/history",
    "top_long_short_ratio": "/api/futures/top-long-short-account-ratio/history"}

@dataclass(frozen=True)
class EndpointDefinition:
    path: str
    category: str

# /// ***********************************************************************************************************************
# /// Classname:          CoinGlassEndpointCatalog
# ///
# /// @brief              Store and resolve supported CoinGlass V4 derivatives endpoint paths
# /// @pre                endpoints must map stable internal keys to CoinGlass API URL paths
# /// @post               Endpoint lookup is available without adding transport logic to the catalog
# /// @param[in]          endpoints: Mapping from internal endpoint keys to provider URL paths
# /// @return             CoinGlassEndpointCatalog class definition
# /// @InOutCorrelation
# /// The catalog keeps endpoint ownership separate from CoinGlassClient. Client code asks for a path by stable
# /// endpoint_key, and the catalog returns the provider path without interpreting payload meaning or market context.
# /// @callsequence       @startuml
# ///                     start
# ///                       :Hold supported endpoint mapping;
# ///                       :Receive endpoint lookup request;
# ///                       :Return matching provider path or None;
# ///                     end
# ///                     @enduml
# /// @traceability
# /// ***********************************************************************************************************************
@dataclass(frozen=True)
class CoinGlassEndpointCatalog:

    endpoints: Mapping[str, str] = field(default_factory=lambda: COINGLASS_ENDPOINTS)

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassEndpointCatalog.get_path(endpoint_key: str)
    # ///
    # /// @brief              Resolve an internal endpoint key to a CoinGlass API path
    # /// @pre                endpoint_key must be a stable internal CoinGlass endpoint identifier
    # /// @post               The catalog state is unchanged
    # /// @param[in]          endpoint_key: Internal endpoint key used by the INPUT layer
    # /// @return             str | None path when the key exists; otherwise None
    # /// @InOutCorrelation
    # /// The method performs only dictionary lookup. A missing key remains a validation concern for the caller,
    # /// usually CoinGlassClient.fetch_endpoint.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Receive endpoint_key;
    # ///                       if (key exists in endpoints?) then (yes)
    # ///                         :Return CoinGlass path;
    # ///                       else (no)
    # ///                         :Return None;
    # ///                       endif
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    def get_path(self, endpoint_key: str) -> str | None:
        return self.endpoints.get(endpoint_key)

    # /// *******************************************************************************************************************
    # /// Functionname:       CoinGlassEndpointCatalog.contains(endpoint_key: str)
    # ///
    # /// @brief              Check whether an internal endpoint key is supported
    # /// @pre                endpoint_key must be a stable internal CoinGlass endpoint identifier
    # /// @post               The catalog state is unchanged
    # /// @param[in]          endpoint_key: Internal endpoint key used by the INPUT layer
    # /// @return             bool True when endpoint_key is present in the catalog
    # /// @InOutCorrelation
    # /// This helper exposes catalog membership without leaking dictionary access to callers. It does not validate
    # /// provider availability, credentials, HTTP state or response payloads.
    # /// @callsequence       @startuml
    # ///                     start
    # ///                       :Receive endpoint_key;
    # ///                       if (key exists in endpoints?) then (yes)
    # ///                         :Return True;
    # ///                       else (no)
    # ///                         :Return False;
    # ///                       endif
    # ///                     end
    # ///                     @enduml
    # /// @traceability
    # /// *******************************************************************************************************************
    def contains(self, endpoint_key: str) -> bool:
        return endpoint_key in self.endpoints
