# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for PebbleService and WorkloadService."""

from unittest.mock import MagicMock, call

import ops

from constants import GRPC_PORT, HTTP_PORT, SERVICE_NAME
from env_vars import DEFAULT_CONTAINER_ENV
from exceptions import WorkloadError
from services import PebbleService, WorkloadService


class _FakeEnvSource:
    def __init__(self, env: dict) -> None:
        self._env = env

    def to_env_vars(self) -> dict:
        return self._env


# ── PebbleService ────────────────────────────────────────────────────────────


def _pebble_service() -> tuple[PebbleService, MagicMock]:
    container = MagicMock()
    return PebbleService(container), container


def test_render_pebble_layer_includes_default_env() -> None:
    svc, _ = _pebble_service()
    layer = svc.render_pebble_layer()
    env = layer.to_dict()["services"][SERVICE_NAME]["environment"]
    for key, value in DEFAULT_CONTAINER_ENV.items():
        assert env[key] == str(value)


def test_render_pebble_layer_merges_sources_in_order() -> None:
    svc, _ = _pebble_service()
    src1 = _FakeEnvSource({"FOO": "from_src1", "BAR": "bar"})
    src2 = _FakeEnvSource({"FOO": "from_src2"})
    layer = svc.render_pebble_layer(src1, src2)
    env = layer.to_dict()["services"][SERVICE_NAME]["environment"]
    assert env["FOO"] == "from_src2"
    assert env["BAR"] == "bar"


def test_render_pebble_layer_has_correct_command() -> None:
    svc, _ = _pebble_service()
    layer = svc.render_pebble_layer()
    cmd = layer.to_dict()["services"][SERVICE_NAME]["command"]
    assert cmd == "/usr/bin/app serve"


def test_render_pebble_layer_has_ready_check() -> None:
    svc, _ = _pebble_service()
    layer = svc.render_pebble_layer()
    checks = layer.to_dict().get("checks", {})
    assert "ready" in checks
    assert checks["ready"]["http"]["url"] == f"http://localhost:{HTTP_PORT}/healthz"


def test_plan_starts_when_service_not_running() -> None:
    svc, container = _pebble_service()
    container.get_service.return_value.is_running.return_value = False
    svc.plan(svc.render_pebble_layer())
    container.start.assert_called_once_with(SERVICE_NAME)
    container.replan.assert_not_called()
    container.restart.assert_not_called()


def test_plan_replans_when_service_running() -> None:
    svc, container = _pebble_service()
    container.get_service.return_value.is_running.return_value = True
    svc.plan(svc.render_pebble_layer())
    container.replan.assert_called_once()
    container.start.assert_not_called()
    container.restart.assert_not_called()


def test_plan_force_restart() -> None:
    svc, container = _pebble_service()
    container.get_service.return_value.is_running.return_value = True
    svc.plan(svc.render_pebble_layer(), force_restart=True)
    container.restart.assert_called_once_with(SERVICE_NAME)
    container.replan.assert_not_called()
    container.start.assert_not_called()


def test_stop_calls_container_stop() -> None:
    svc, container = _pebble_service()
    container.can_connect.return_value = True
    svc.stop()
    container.stop.assert_called_once_with(SERVICE_NAME)


def test_stop_does_not_raise_on_error() -> None:
    svc, container = _pebble_service()
    container.can_connect.return_value = True
    container.stop.side_effect = RuntimeError("pebble error")
    svc.stop()  # should not raise


# ── WorkloadService ───────────────────────────────────────────────────────────


def _workload_service() -> tuple[WorkloadService, MagicMock, MagicMock, MagicMock]:
    unit = MagicMock()
    cli = MagicMock()
    container = MagicMock()
    return WorkloadService(unit, cli, container), unit, cli, container


def test_update_workload_version_sets_version() -> None:
    svc, unit, cli, _ = _workload_service()
    cli.get_service_version.return_value = "1.2.3"
    svc.update_workload_version()
    unit.set_workload_version.assert_called_once_with("1.2.3")


def test_update_workload_version_noop_when_empty() -> None:
    svc, unit, cli, _ = _workload_service()
    cli.get_service_version.return_value = ""
    svc.update_workload_version()
    unit.set_workload_version.assert_not_called()


def test_update_workload_version_absorbs_exception() -> None:
    svc, unit, cli, _ = _workload_service()
    cli.get_service_version.side_effect = WorkloadError("exec failed")
    svc.update_workload_version()  # should not raise


def test_update_workload_version_absorbs_set_version_exception() -> None:
    svc, unit, cli, _ = _workload_service()
    cli.get_service_version.return_value = "1.0.0"
    unit.set_workload_version.side_effect = RuntimeError("juju error")
    svc.update_workload_version()  # should not raise


def test_is_running_true() -> None:
    svc, _, _, container = _workload_service()
    container.get_service.return_value.is_running.return_value = True
    assert svc.is_running() is True


def test_is_running_false() -> None:
    svc, _, _, container = _workload_service()
    container.get_service.return_value.is_running.return_value = False
    assert svc.is_running() is False


def test_is_running_returns_false_on_exception() -> None:
    svc, _, _, container = _workload_service()
    container.get_service.side_effect = RuntimeError
    assert svc.is_running() is False


def test_is_failing_false_when_check_up() -> None:
    svc, _, _, container = _workload_service()
    container.get_check.return_value.status = ops.pebble.CheckStatus.UP
    assert svc.is_failing() is False


def test_is_failing_true_when_check_down() -> None:
    svc, _, _, container = _workload_service()
    container.get_check.return_value.status = ops.pebble.CheckStatus.DOWN
    assert svc.is_failing() is True


def test_open_port_opens_both_ports() -> None:
    svc, unit, _, _ = _workload_service()
    svc.open_port()
    assert call("tcp", HTTP_PORT) in unit.open_port.call_args_list
    assert call("tcp", GRPC_PORT) in unit.open_port.call_args_list
