# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for CommandLine CLI wrapper."""

from unittest.mock import MagicMock

import ops.pebble
import pytest

from cli import CommandLine
from exceptions import WorkloadError


def _make_cli(
    exec_result: tuple[str, str] | None = None, exit_code: int = 0
) -> tuple[CommandLine, MagicMock]:
    container = MagicMock()
    if exec_result is not None:
        process = MagicMock()
        process.wait_output.return_value = exec_result
        container.exec.return_value = process
    if exit_code != 0:
        err = ops.pebble.ExecError(["cmd"], exit_code, "", "error output")
        container.exec.side_effect = err
    return CommandLine(container), container


def test_get_service_version_success() -> None:
    cli, container = _make_cli(exec_result=("v1.2.3\n", ""))
    version = cli.get_service_version()
    assert version == "v1.2.3"
    container.exec.assert_called_once()
    cmd = container.exec.call_args[0][0]
    assert cmd == ["/usr/bin/app", "version"]


def test_get_service_version_raises_on_failure() -> None:
    cli, _ = _make_cli(exit_code=1)
    with pytest.raises(WorkloadError):
        cli.get_service_version()


def test_run_migration_success() -> None:
    dsn = "postgresql://user:pass@host:5432/db"
    cli, container = _make_cli(exec_result=("Migration complete\n", ""))
    cli.run_migration(dsn)
    cmd = container.exec.call_args[0][0]
    assert cmd == ["/usr/bin/app", "migrate", "--dsn", dsn]


def test_run_migration_raises_on_failure() -> None:
    cli, _ = _make_cli(exit_code=1)
    with pytest.raises(WorkloadError):
        cli.run_migration("postgresql://user:pass@host:5432/db")


def test_migrate_status_returns_true_when_pending() -> None:
    cli, container = _make_cli(exec_result=("2 migrations pending\n", ""))
    assert cli.migrate_status() is True


def test_migrate_status_returns_false_when_up_to_date() -> None:
    cli, container = _make_cli(exec_result=("No migrations needed\n", ""))
    assert cli.migrate_status() is False


def test_migrate_status_returns_true_on_exit_code_1() -> None:
    container = MagicMock()
    err = ops.pebble.ExecError(["/usr/bin/app", "migrate", "status"], 1, "", "")
    container.exec.side_effect = err
    cli = CommandLine(container)
    assert cli.migrate_status() is True


def test_migrate_status_raises_on_unexpected_error() -> None:
    container = MagicMock()
    err = ops.pebble.ExecError(
        ["/usr/bin/app", "migrate", "status"], 2, "", "db connection failed"
    )
    container.exec.side_effect = err
    cli = CommandLine(container)
    with pytest.raises(WorkloadError):
        cli.migrate_status()
