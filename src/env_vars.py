# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""EnvVarConvertible protocol and default container environment."""

from typing import Mapping, Protocol, TypeAlias

from constants import GRPC_PORT, HTTP_PORT

EnvVars: TypeAlias = Mapping[str, str | bool | int]

DEFAULT_CONTAINER_ENV: EnvVars = {
    "GRPC_PORT": str(GRPC_PORT),
    "HTTP_PORT": str(HTTP_PORT),
    "LOG_FORMAT": "json",
    "TELEMETRY_ENABLED": "false",
    "OTEL_SERVICE_NAME": "authorization-service",
}


class EnvVarConvertible(Protocol):
    """Protocol for objects that can produce workload environment variables."""

    def to_env_vars(self) -> EnvVars:
        """Return a mapping of environment variable names to values."""
        ...
