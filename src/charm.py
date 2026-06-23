#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for the Canonical Authorization Service Server (Cerberus)."""

import logging
from functools import cached_property

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.oauth2_proxy_k8s.v0.forward_auth import ForwardAuthConfig, ForwardAuthProvider
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from charms.openfga_k8s.v1.openfga import (
    OpenFGARequires,
    OpenFGAStoreRemovedEvent,
)
from charms.secure_token_service.v0.sts_info import StsInfoRequirer
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer

from cli import CommandLine
from configs import CharmConfig
from constants import (
    CONTAINER_NAME,
    FORWARD_AUTH_INTEGRATION_NAME,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    GRPC_PORT,
    INGRESS_INTEGRATION_NAME,
    LOGGING_INTEGRATION_NAME,
    MIGRATION_COMPLETED,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    OPENFGA_STORE_NAME,
    PEER_INTEGRATION_NAME,
    PG_DATABASE_INTEGRATION_NAME,
    STS_INFO_INTEGRATION_NAME,
    TRACING_INTEGRATION_NAME,
)
from exceptions import CreateFgaModelError, IntegrationDataError, WorkloadError
from integrations import (
    DatabaseConfig,
    IstioIngressIntegration,
    OpenFGAIntegration,
    OpenFGAModelData,
    PeerData,
    StsConfig,
    TracingConfig,
)
from services import PebbleService, WorkloadService
from utils import container_connectivity, openfga_store_readiness, peer_integration_exists

logger = logging.getLogger(__name__)


class AuthorizationServiceCharm(ops.CharmBase):
    """Charm for the Canonical Authorization Service.

    This charm is the server in the server-consumer architecture, providing
    a Policy Decision Point for the Canonical centralized identity platform.
    """

    def __init__(self, *args: object) -> None:
        """Initialize the charm."""
        super().__init__(*args)

        container = self.unit.get_container(CONTAINER_NAME)
        self._cli = CommandLine(container)
        self._pebble_service = PebbleService(container)
        self._workload_service = WorkloadService(self.unit, self._cli, container)
        self.peer_data = PeerData(self.model)
        self._charm_config = CharmConfig(self.model.config)

        # Kubernetes resource patch
        self.resources_patch = KubernetesComputeResourcesPatch(
            self,
            CONTAINER_NAME,
            resource_reqs_func=self._resource_reqs_from_config,
        )

        # Integration helpers
        self._database = DatabaseRequires(
            self,
            relation_name=PG_DATABASE_INTEGRATION_NAME,
            database_name="cerberus",
        )
        self._openfga_requirer = OpenFGARequires(
            self, store_name=OPENFGA_STORE_NAME, relation_name=OPENFGA_INTEGRATION_NAME
        )
        self.openfga_integration = OpenFGAIntegration(self._openfga_requirer)

        self._sts = StsInfoRequirer(self, relation_name=STS_INFO_INTEGRATION_NAME)

        # Ingress
        self.istio_ingress = IstioIngressIntegration(self, relation_name=INGRESS_INTEGRATION_NAME)
        self._forward_auth = ForwardAuthProvider(
            self,
            relation_name=FORWARD_AUTH_INTEGRATION_NAME,
            forward_auth_config=ForwardAuthConfig(
                # grpc:// scheme is used so urlparse() on the istio side correctly extracts hostname and port
                decisions_address=f"grpc://{self.app.name}.{self.model.name}.svc.cluster.local:{GRPC_PORT}",
                app_names=[self.app.name],
            ),
        )

        # Observability
        self._tracing = TracingEndpointRequirer(
            self, relation_name=TRACING_INTEGRATION_NAME, protocols=["otlp_http", "otlp_grpc"]
        )
        self._logging = LogForwarder(self, relation_name=LOGGING_INTEGRATION_NAME)
        self._grafana_dashboard = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_INTEGRATION_NAME
        )

        # Lifecycle events
        self.framework.observe(self.on.config_changed, self._on_holistic_handler)
        self.framework.observe(
            self.on.authorization_service_pebble_ready,
            self._on_pebble_ready,
        )
        self.framework.observe(self.on.upgrade_charm, self._on_holistic_handler)

        # Database events
        self.framework.observe(self._database.on.database_created, self._on_holistic_handler)
        self.framework.observe(self._database.on.endpoints_changed, self._on_holistic_handler)
        self.framework.observe(
            self.on[PG_DATABASE_INTEGRATION_NAME].relation_broken,
            self._on_database_relation_broken,
        )

        # OpenFGA events
        self.framework.observe(
            self._openfga_requirer.on.openfga_store_created, self._on_holistic_handler
        )
        self.framework.observe(
            self._openfga_requirer.on.openfga_store_removed, self._on_openfga_store_removed
        )

        # Tracing events
        self.framework.observe(
            self.on[TRACING_INTEGRATION_NAME].relation_changed, self._on_holistic_handler
        )
        self.framework.observe(
            self.on[TRACING_INTEGRATION_NAME].relation_broken, self._on_holistic_handler
        )

        # STS events
        self.framework.observe(self._sts.on.sts_info_relation_updated, self._on_holistic_handler)
        self.framework.observe(self._sts.on.sts_info_relation_broken, self._on_holistic_handler)

        # Ingress events
        self.framework.observe(self.istio_ingress.requirer.on.ready, self._on_ingress_ready)

        # Resources patch event
        self.framework.observe(
            self.resources_patch.on.patch_failed, self._on_resource_patch_failed
        )

        # Action events
        self.framework.observe(self.on.run_migration_action, self._on_run_migration_action)

        # Peer relation events
        self.framework.observe(
            self.on[PEER_INTEGRATION_NAME].relation_created, self._on_holistic_handler
        )
        self.framework.observe(
            self.on[PEER_INTEGRATION_NAME].relation_changed, self._on_holistic_handler
        )

        # Status collection
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

    # --- Properties ---

    @cached_property
    def _database_config(self) -> DatabaseConfig:
        """Database config from relation data, computed once per event dispatch."""
        return DatabaseConfig.load(self._database)

    @cached_property
    def _workload_version(self) -> str:
        """Workload version string, computed once per event dispatch."""
        return self._workload_service.version

    @property
    def _migration_pending(self) -> bool:
        """True if the database migration has not been completed for the current version.

        Uses the CLI to check migration status. Falls back to False on any error.
        """
        if not self._database_config.is_ready:
            return False
        try:
            return self._cli.migrate_status()
        except WorkloadError as exc:
            logger.error("Failed to check migration status: %s", exc)
            return False

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """Pebble layer with all available env var sources merged."""
        return self._pebble_service.render_pebble_layer(
            self._charm_config,
            self._database_config,
            self.openfga_integration.openfga_integration_data,
            OpenFGAModelData.load(self.peer_data[self._workload_version]),
            StsConfig.load(self._sts),
            TracingConfig.load(self._tracing),
        )

    # --- Helpers ---

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        """Build resource requirements from charm config."""
        limits = {"cpu": self.model.config.get("cpu"), "memory": self.model.config.get("memory")}
        requests = {"cpu": "100m", "memory": "200Mi"}
        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)

    def _ensure_openfga_model(self) -> bool:
        """Ensure the OpenFGA authorization model is created and stored in peer data.

        Returns:
            True when the model ID is available (already created or just created),
            False when a prerequisite is not yet satisfied.
        """
        if not openfga_store_readiness(self):
            return False
        if not peer_integration_exists(self):
            return False

        version = self._workload_version
        if not version:
            return False
        if self.peer_data[version].get(OPENFGA_MODEL_ID):
            return True

        if not self.unit.is_leader():
            return False

        try:
            model_id = self._workload_service.create_openfga_model(
                self.openfga_integration.openfga_integration_data.store_id
            )
        except (CreateFgaModelError, IntegrationDataError):
            logger.exception("Failed to create OpenFGA model")
            return False

        self.peer_data[version] = {OPENFGA_MODEL_ID: model_id}
        return True

    # --- Event handlers ---

    def _on_holistic_handler(self, event: ops.HookEvent) -> None:
        """Apply workload configuration when all prerequisites are satisfied.

        Args:
            event: The triggering hook event.
        """
        if self.unit.is_leader() and self.istio_ingress.requirer.is_ready():
            self.istio_ingress.submit_routes()

        if not container_connectivity(self):
            return
        if not self._database_config.is_ready:
            return
        if self._migration_pending:
            return
        if not openfga_store_readiness(self):
            return
        if not self._ensure_openfga_model():
            return

        self._pebble_service.plan(self._pebble_layer)

    def _on_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """Handle Pebble ready event.

        Args:
            event: The pebble_ready event.
        """
        self._workload_service.open_port()
        self._on_holistic_handler(event)
        self._workload_service.update_workload_version()

    def _on_database_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle database relation broken.

        Args:
            event: The relation broken event.
        """
        self._pebble_service.stop()
        self._on_holistic_handler(event)

    def _on_openfga_store_removed(self, event: OpenFGAStoreRemovedEvent) -> None:
        """Handle OpenFGA store removed — stop the workload.

        Args:
            event: The store-removed event.
        """
        self._pebble_service.stop()
        self._on_holistic_handler(event)

    def _on_ingress_ready(self, event: ops.HookEvent) -> None:
        """Handle ingress ready event.

        Args:
            event: The ingress ready event.
        """
        external_url = self.istio_ingress.external_url
        logger.info("Ingress ready: %s", external_url or "(none)")
        self._on_holistic_handler(event)

    def _on_run_migration_action(self, event: ops.ActionEvent) -> None:
        """Run database migrations (leader unit only).

        Args:
            event: The run-migration action event.
        """
        if not self.unit.is_leader():
            event.fail("Only the leader can run migrations")
            return

        if not container_connectivity(self):
            event.fail("Container is not ready")
            return

        db = self._database_config
        if not db.is_ready:
            event.fail("Database integration is not ready")
            return

        try:
            self._cli.run_migration(db.dsn)
        except WorkloadError as exc:
            event.fail(str(exc))
            return

        # Writing to peer data triggers peer_relation_changed on all units,
        # allowing non-leader units to re-evaluate and proceed via the holistic handler.
        self.peer_data[MIGRATION_COMPLETED] = self._workload_service.version
        self._on_holistic_handler(event)

    def _on_resource_patch_failed(self, event: K8sResourcePatchFailedEvent) -> None:
        """Handle the resource-patch-failed event.

        Args:
            event: The patch_failed event.
        """
        logger.error("Resource patching failed: %s", event.message)
        self._on_holistic_handler(event)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Report the current unit status.

        Args:
            event: The collect-unit-status event.
        """
        if missing := self._charm_config.get_missing_config_keys():
            event.add_status(ops.BlockedStatus(f"Invalid configuration: {missing}"))

        event.add_status(self.resources_patch.get_status())

        if not container_connectivity(self):
            event.add_status(ops.WaitingStatus("Waiting for container"))

        if not peer_integration_exists(self):
            event.add_status(ops.WaitingStatus("Waiting for peer integration"))

        if self._migration_pending:
            event.add_status(ops.BlockedStatus("Waiting for database migration"))

        if not self.model.relations.get(PG_DATABASE_INTEGRATION_NAME):
            event.add_status(
                ops.BlockedStatus(f"Missing required relation: {PG_DATABASE_INTEGRATION_NAME}")
            )

        if not self._database_config.is_ready:
            event.add_status(ops.WaitingStatus("Waiting for database credentials"))

        if not self.model.relations.get(OPENFGA_INTEGRATION_NAME):
            event.add_status(
                ops.BlockedStatus(f"Missing required relation: {OPENFGA_INTEGRATION_NAME}")
            )

        if not openfga_store_readiness(self):
            event.add_status(ops.WaitingStatus("OpenFGA store is not ready yet"))

        if not self._workload_service.is_running():
            event.add_status(ops.WaitingStatus("Waiting for workload to start"))

        event.add_status(ops.ActiveStatus())


if __name__ == "__main__":
    ops.main(AuthorizationServiceCharm)
