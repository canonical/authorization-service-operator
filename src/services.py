# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Service layer: PebbleService and WorkloadService."""

import logging
from typing import TYPE_CHECKING

import ops
from ops.pebble import Layer, LayerDict

from constants import GRPC_PORT, HTTP_PORT, SERVICE_NAME
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible

if TYPE_CHECKING:
    from cli import CommandLine

logger = logging.getLogger(__name__)

PEBBLE_LAYER_DICT: LayerDict = {
    "summary": "authorization-service layer",
    "services": {
        SERVICE_NAME: {
            "override": "replace",
            "summary": "Authorization Service",
            "command": "/usr/bin/app serve",
            "startup": "disabled",
            "on-check-failure": {"ready": "restart"},
        }
    },
    "checks": {
        "ready": {
            "override": "replace",
            "level": "ready",
            "http": {"url": f"http://localhost:{HTTP_PORT}/healthz"},
        }
    },
}


class PebbleService:
    """Encapsulates Pebble operations for the authorization-service container.

    Args:
        container: The Pebble container to manage.
    """

    def __init__(self, container: ops.Container) -> None:
        self._container = container

    def render_pebble_layer(self, *env_var_sources: EnvVarConvertible) -> Layer:
        """Build the Pebble layer by merging environment variable sources.

        Args:
            *env_var_sources: Objects implementing EnvVarConvertible. Their
                to_env_vars() outputs are merged in order over DEFAULT_CONTAINER_ENV.

        Returns:
            A Pebble Layer with the merged environment.
        """
        env: dict[str, str] = {k: str(v) for k, v in DEFAULT_CONTAINER_ENV.items()}
        for source in env_var_sources:
            env.update({k: str(v) for k, v in source.to_env_vars().items()})

        layer_dict: LayerDict = dict(PEBBLE_LAYER_DICT)  # type: ignore[assignment]
        layer_dict = {
            **PEBBLE_LAYER_DICT,
            "services": {
                SERVICE_NAME: {
                    **PEBBLE_LAYER_DICT["services"][SERVICE_NAME],  # type: ignore[index]
                    "environment": env,
                }
            },
        }
        return Layer(layer_dict)

    def plan(self, layer: Layer, force_restart: bool = False) -> None:
        """Apply the Pebble layer and start or restart the service.

        Args:
            layer: The layer to apply.
            force_restart: If True, restart regardless of current state.
        """
        self._container.add_layer(SERVICE_NAME, layer, combine=True)
        self._restart_service(restart=force_restart)

    def _restart_service(self, restart: bool = False) -> None:
        """Start or restart the Pebble service.

        Args:
            restart: If True, force a restart. Otherwise start if stopped,
                or replan if already running.
        """
        if restart:
            self._container.restart(SERVICE_NAME)
        elif not self._container.get_service(SERVICE_NAME).is_running():
            self._container.start(SERVICE_NAME)
        else:
            self._container.replan()

    def stop(self) -> None:
        """Stop the authorization-service Pebble service."""
        try:
            if self._container.can_connect():
                self._container.stop(SERVICE_NAME)
                logger.debug("Service %s stopped", SERVICE_NAME)
        except Exception as e:
            logger.warning("Failed to stop service %s: %s", SERVICE_NAME, e)


class WorkloadService:
    """Manages the authorization-service workload.

    Args:
        unit: The Juju unit.
        cli: The CommandLine wrapper.
        container: The Pebble container.
    """

    def __init__(self, unit: ops.Unit, cli: "CommandLine", container: ops.Container) -> None:
        self._unit = unit
        self._cli = cli
        self._container = container

    @property
    def version(self) -> str:
        """Workload version string."""
        return self._cli.get_service_version()

    def update_workload_version(self) -> None:
        """Set the workload version on the unit; absorbs all errors."""
        try:
            v = self.version
            if v:
                self._unit.set_workload_version(v)
        except Exception as e:
            logger.error("Failed to update workload version: %s", e)

    def is_running(self) -> bool:
        """Return True if the service is running and the ready check passes."""
        try:
            svc = self._container.get_service(SERVICE_NAME)
            return svc.is_running()
        except Exception:
            return False

    def is_failing(self) -> bool:
        """Return True if the ready check is in a failure state."""
        try:
            check = self._container.get_check("ready")
            return check.status == ops.pebble.CheckStatus.DOWN
        except Exception:
            return False

    def open_port(self) -> None:
        """Open HTTP and gRPC ports on the unit."""
        self._unit.open_port("tcp", HTTP_PORT)
        self._unit.open_port("tcp", GRPC_PORT)

    def create_openfga_model(self, store_id: str) -> str:
        """Write the OpenFGA authorization model and return its ID.

        Args:
            store_id: The OpenFGA store ID to write the model into.

        Returns:
            The authorization model ID.

        Raises:
            CreateFgaModelError: If the model creation fails.
        """
        return self._cli.create_openfga_model(store_id)
