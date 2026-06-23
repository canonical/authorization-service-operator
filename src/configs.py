# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm configuration helper."""

from ops import ConfigData

from env_vars import EnvVars

_VALID_LOG_LEVELS = frozenset({"debug", "info", "warn", "error"})


class CharmConfig:
    """Wraps charm :class:`ops.ConfigData` with typed access and env-var conversion."""

    def __init__(self, config: ConfigData) -> None:
        self._config = config

    def get_missing_config_keys(self) -> list[str]:
        """Return a list of human-readable messages for invalid config values.

        Returns:
            An empty list when all config values are valid; otherwise one entry
            per invalid key describing the problem.
        """
        issues = []
        log_level = self._config.get("log_level", "info")
        if log_level not in _VALID_LOG_LEVELS:
            issues.append(f"log_level={log_level!r} (must be one of {sorted(_VALID_LOG_LEVELS)})")
        return issues

    def to_env_vars(self) -> EnvVars:
        """Return environment variables derived from charm config.

        Returns:
            Mapping of env var names to values. Unset optional fields are omitted.
            cpu and memory are NOT included — handled by KubernetesComputeResourcesPatch.
        """
        return {
            "LOG_LEVEL": str(self._config.get("log_level", "info")),
            "DEV": str(bool(self._config.get("dev", False))).lower(),
            "HTTP_PROXY": self._config.get("http_proxy"),
            "HTTPS_PROXY": self._config.get("https_proxy"),
            "NO_PROXY": self._config.get("no_proxy"),
        }
