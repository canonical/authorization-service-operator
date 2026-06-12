# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom exception hierarchy for the Authorization Service charm."""


class AuthorizationServiceCharmError(Exception):
    """Base exception for all Authorization Service charm errors."""


class ConfigError(AuthorizationServiceCharmError):
    """Raised when charm configuration is invalid."""


class IntegrationDataError(AuthorizationServiceCharmError):
    """Raised when relation databag data is missing or malformed."""


class WorkloadError(AuthorizationServiceCharmError):
    """Raised when a workload operation (CLI exec, Pebble) fails."""


class CreateFgaModelError(AuthorizationServiceCharmError):
    """Raised when the OpenFGA authorization model creation fails."""
