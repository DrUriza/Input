# \file **********************************************************************
# COMPANY:            Ealtin
# PROJECT:            Trading-Elatin-Platform
# COMPONENT:          Input - Common
# MODULE NAME:        errors.py
# DESCRIPTION:        @brief Common exceptions for external input providers
# AUTHOR:             Dr. Ottmar Uriza
# CREATION DATE:      08.05.2026
# VERSION:            $Revision: 0.1$
# CHANGES:            08.05.2026 - Initial error contracts
# *************************************************************************


class InputProviderError(Exception):
    """@brief Base exception for raw input provider failures."""


class InputValidationError(InputProviderError):
    """@brief Raised when a provider response fails minimal structural validation."""
