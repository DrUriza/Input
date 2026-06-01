# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - CoinGlass
# MODULE NAME:        coinglass_models.py
# DESCRIPTION:        @brief Raw CoinGlass request contracts
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial CoinGlass request model
#                     09.05.2026 - Added optional raw request parameters
# *************************************************************************
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# /// ***********************************************************************************************************************
# /// Classname:          CoinGlassRequest
# ///
# /// @brief              Store the raw request contract for one CoinGlass derivatives endpoint call
# /// @pre                endpoint_key must be resolved by CoinGlassEndpointCatalog before provider transport
# /// @post               Request values remain immutable after construction
# /// @param[in]          endpoint_key: Stable internal endpoint identifier
# /// @param[in]          symbol: Optional asset symbol requested from CoinGlass
# /// @param[in]          params: Provider query parameters passed through without feature normalization
# /// @param[in]          exchange: Optional exchange name included in query params by CoinGlassClient
# /// @param[in]          interval: Optional history interval included in query params by CoinGlassClient
# /// @param[in]          limit: Optional maximum number of records included in query params by CoinGlassClient
# /// @return             CoinGlassRequest dataclass definition
# /// @InOutCorrelation
# /// The request model represents only INPUT-layer provider arguments. It contains no market signal, sentiment,
# /// score, feature-normalization result, bullish/bearish interpretation, or trading decision field.
# /// @callsequence       @startuml
# ///                     start
# ///                       :Receive endpoint_key and optional raw parameters;
# ///                       :Freeze request contract;
# ///                       :Pass request to CoinGlassClient.fetch_endpoint;
# ///                     end
# ///                     @enduml
# /// @traceability
# /// ***********************************************************************************************************************
@dataclass(frozen=True)
class CoinGlassRequest:

    endpoint_key: str
    symbol: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    exchange: str | None = None
    interval: str | None = None
    limit: int | None = None
