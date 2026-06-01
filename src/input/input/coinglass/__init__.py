# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - CoinGlass
# MODULE NAME:        __init__.py
# DESCRIPTION:        @brief CoinGlass aggregated market-data input contracts
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial CoinGlass package
#                     09.05.2026 - Exported CoinGlass endpoint catalog object
# *************************************************************************
from .coinglass_client import CoinGlassClient
from .coinglass_endpoints import COINGLASS_ENDPOINTS, CoinGlassEndpointCatalog
from .coinglass_models import CoinGlassRequest

__all__ = ["COINGLASS_ENDPOINTS", "CoinGlassClient", "CoinGlassEndpointCatalog", "CoinGlassRequest"]
