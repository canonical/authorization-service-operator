# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for CharmConfig."""

from configs import CharmConfig


class _FakeConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _cfg(config: dict) -> CharmConfig:
    return CharmConfig(_FakeConfig(config))


def test_valid_log_levels() -> None:
    for level in ("debug", "info", "warn", "error"):
        cfg = _cfg({"log_level": level})
        assert cfg.get_missing_config_keys() == []


def test_invalid_log_level_in_missing_keys() -> None:
    cfg = _cfg({"log_level": "verbose"})
    missing = cfg.get_missing_config_keys()
    assert len(missing) == 1
    assert "log_level" in missing[0]


def test_to_env_vars_includes_required_fields() -> None:
    cfg = _cfg({"log_level": "debug", "dev": True})
    env = cfg.to_env_vars()
    assert env["LOG_LEVEL"] == "debug"
    assert env["DEV"] == "true"


def test_to_env_vars_unset_proxy_fields_are_none() -> None:
    cfg = _cfg({"log_level": "info"})
    env = cfg.to_env_vars()
    assert env["HTTP_PROXY"] is None
    assert env["HTTPS_PROXY"] is None
    assert env["NO_PROXY"] is None


def test_to_env_vars_includes_set_proxy_fields() -> None:
    cfg = _cfg({
        "log_level": "info",
        "http_proxy": "http://proxy:3128",
        "no_proxy": "localhost",
    })
    env = cfg.to_env_vars()
    assert env["HTTP_PROXY"] == "http://proxy:3128"
    assert env["NO_PROXY"] == "localhost"
    assert env["HTTPS_PROXY"] is None


def test_to_env_vars_excludes_cpu_and_memory() -> None:
    cfg = _cfg({"log_level": "info", "cpu": "500m", "memory": "256Mi"})
    env = cfg.to_env_vars()
    assert "cpu" not in env
    assert "memory" not in env
    assert "CPU" not in env
    assert "MEMORY" not in env
