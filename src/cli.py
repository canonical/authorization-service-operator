# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI wrapper for the /usr/bin/app binary via Pebble exec."""

import json
import logging
from dataclasses import dataclass

import ops

from constants import APP_BINARY, SERVICE_NAME
from exceptions import CreateFgaModelError, WorkloadError

logger = logging.getLogger(__name__)


@dataclass
class CmdExecConfig:
    """Configuration for a Pebble exec command.

    Attributes:
        service_context: The Pebble service context to exec within.
        environment: Extra environment variables for the process.
        timeout: Maximum seconds to wait for the command.
        stdin: Optional stdin content.
    """

    service_context: str
    environment: dict[str, str]
    timeout: int
    stdin: str | None = None


class CommandLine:
    """Wraps the /usr/bin/app binary via Pebble exec.

    Args:
        container: The Pebble container to exec within.
    """

    def __init__(self, container: ops.Container) -> None:
        self._container = container

    def _run_cmd(self, cmd: list[str], exec_config: CmdExecConfig) -> tuple[str, str]:
        """Run a command via Pebble exec and return (stdout, stderr).

        Args:
            cmd: Command and arguments.
            exec_config: Execution configuration.

        Returns:
            Tuple of (stdout, stderr) strings.

        Raises:
            WorkloadError: If the command exits with a non-zero status.
        """
        try:
            process = self._container.exec(
                cmd,
                service_context=exec_config.service_context,
                environment=exec_config.environment,
                timeout=exec_config.timeout,
                stdin=exec_config.stdin,
            )
            stdout, stderr = process.wait_output()
            return stdout, stderr
        except ops.pebble.ExecError as e:
            raise WorkloadError(
                f"Command {cmd} failed with exit code {e.exit_code}: {e.stderr}"
            ) from e
        except Exception as e:
            raise WorkloadError(f"Command {cmd} failed: {e}") from e

    def _default_config(self) -> CmdExecConfig:
        return CmdExecConfig(
            service_context=SERVICE_NAME,
            environment={},
            timeout=30,
        )

    def get_service_version(self) -> str:
        """Return the workload version string.

        Returns:
            Version string from `/usr/bin/app version`.

        Raises:
            WorkloadError: If the command fails.
        """
        stdout, _ = self._run_cmd([APP_BINARY, "version"], self._default_config())
        return stdout.strip()

    def run_migration(self, dsn: str) -> None:
        """Run database migrations.

        Args:
            dsn: The PostgreSQL DSN connection string.

        Raises:
            WorkloadError: If the migration command exits non-zero.
        """
        config = CmdExecConfig(
            service_context=SERVICE_NAME,
            environment={},
            timeout=120,
        )
        self._run_cmd([APP_BINARY, "migrate", "--dsn", dsn], config)

    def migrate_status(self) -> bool:
        """Check whether a database migration is pending.

        Returns:
            True if migration is needed, False if up-to-date.

        Raises:
            WorkloadError: On unexpected failure.
        """
        try:
            stdout, _ = self._run_cmd([APP_BINARY, "migrate", "status"], self._default_config())
            return "pending" in stdout.lower()
        except WorkloadError as e:
            if "exit code 1" in str(e):
                return True
            raise

    def create_openfga_model(self, store_id: str) -> str:
        """Write the OpenFGA authorization model and return its ID.

        The OpenFGA connection details (address, API key) are read from the
        container's environment variables set by the Pebble layer.

        Args:
            store_id: The OpenFGA store ID to write the model into.

        Returns:
            The authorization model ID.

        Raises:
            CreateFgaModelError: If the command fails or the model ID cannot
                be found in the output.
        """
        config = CmdExecConfig(
            service_context=SERVICE_NAME,
            environment={},
            timeout=60,
        )
        try:
            _, stderr = self._run_cmd([APP_BINARY, "write-model", store_id], config)
        except WorkloadError as err:
            logger.error("Failed to write OpenFGA model: %s", err)
            raise CreateFgaModelError from err

        for line in stderr.splitlines():
            try:
                if model_id := json.loads(line).get("model_id"):
                    return model_id
            except json.JSONDecodeError:
                continue

        raise CreateFgaModelError("write-model output did not contain a model_id")
