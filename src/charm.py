#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for the Canonical Authorization Service Server."""

import logging
from functools import cached_property

import ops
from authorization_service_operator_shared.cli import CommandLine
from authorization_service_operator_shared.configs import CharmConfig
from authorization_service_operator_shared.database import (
    DatabaseConfig,
    DatabaseRelationHandler,
)
from authorization_service_operator_shared.exceptions import (
    CreateFgaModelError,
    IntegrationDataError,
    WorkloadError,
)
from authorization_service_operator_shared.info import AuthorizationServiceInfoProvider
from authorization_service_operator_shared.ingress import IstioIngressIntegration
from authorization_service_operator_shared.observability import TracingConfig
from authorization_service_operator_shared.openfga import OpenFGAModelData, OpenFGARelationHandler
from authorization_service_operator_shared.peer import PeerData
from authorization_service_operator_shared.services import (
    PebbleService,
    WorkloadService,
)
from authorization_service_operator_shared.sts import STSRelationHandler
from authorization_service_operator_shared.utils import container_connectivity
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.oauth2_proxy_k8s.v0.forward_auth import ForwardAuthConfig, ForwardAuthProvider
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from charms.openfga_k8s.v1.openfga import OpenFGARequires, OpenFGAStoreRemovedEvent
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer

from constants import (
    AUTHORIZATION_SERVICE_INFO_INTEGRATION_NAME,
    CONTAINER_NAME,
    FORWARD_AUTH_INTEGRATION_NAME,
    GRAFANA_DASHBOARD_INTEGRATION_NAME,
    GRPC_PORT,
    INGRESS_INTEGRATION_NAME,
    LOGGING_INTEGRATION_NAME,
    MIGRATION_COMPLETED,
    OPENFGA_INTEGRATION_NAME,
    OPENFGA_MODEL_ID,
    PEER_INTEGRATION_NAME,
    PG_DATABASE_INTEGRATION_NAME,
    STS_INFO_INTEGRATION_NAME,
    TRACING_INTEGRATION_NAME,
)

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
        self._pebble_service = PebbleService(
            container,
            service_name=CONTAINER_NAME,
            command="/usr/bin/app serve",
        )
        self._workload_service = WorkloadService(
            self.unit,
            self._cli,
            container,
            service_name=CONTAINER_NAME,
        )
        self.peer_data = PeerData(self.model)
        self._charm_config = CharmConfig(self.model.config)

        # Kubernetes resource patch
        self.resources_patch = KubernetesComputeResourcesPatch(
            self,
            CONTAINER_NAME,
            resource_reqs_func=self._resource_reqs_from_config,
        )

        # Integration helpers
        self._database = DatabaseRelationHandler(
            self,
            relation_name=PG_DATABASE_INTEGRATION_NAME,
            database_name="authorization_service",
        )

        self._openfga_requires = OpenFGARequires(
            self,
            store_name="authorization-service",
            relation_name=OPENFGA_INTEGRATION_NAME,
        )
        self._openfga = OpenFGARelationHandler(self._openfga_requires)

        self._sts = STSRelationHandler(
            self,
            relation_name=STS_INFO_INTEGRATION_NAME,
        )

        self.authz_info_provider = AuthorizationServiceInfoProvider(
            self,
            relation_name=AUTHORIZATION_SERVICE_INFO_INTEGRATION_NAME,
        )

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
        self.framework.observe(
            self._database.postgres.on.database_created, self._on_holistic_handler
        )
        self.framework.observe(
            self._database.postgres.on.endpoints_changed, self._on_holistic_handler
        )
        self.framework.observe(
            self.on[PG_DATABASE_INTEGRATION_NAME].relation_broken,
            self._on_database_relation_broken,
        )

        # OpenFGA events
        self.framework.observe(
            self._openfga_requires.on.openfga_store_created, self._on_holistic_handler
        )
        self.framework.observe(
            self._openfga_requires.on.openfga_store_removed, self._on_openfga_store_removed
        )

        # Tracing events
        self.framework.observe(
            self._tracing.on.endpoint_changed, self._on_holistic_handler
        )
        self.framework.observe(
            self._tracing.on.endpoint_removed, self._on_holistic_handler
        )

        # STS events
        self.framework.observe(
            self._sts.requirer.on.sts_info_relation_updated, self._on_holistic_handler
        )
        self.framework.observe(
            self._sts.requirer.on.sts_info_relation_broken, self._on_holistic_handler
        )

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

        # Authorization service info relation events
        self.framework.observe(
            self.authz_info_provider.on.authorization_service_info_relation_ready,
            self._on_holistic_handler,
        )

        # Status collection
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

    # --- Properties ---

    @cached_property
    def _workload_version(self) -> str:
        """Workload version string, computed once per event dispatch."""
        return self._workload_service.version

    @cached_property
    def _migration_pending(self) -> bool:
        """True if the database migration has not been completed for the current version.

        Uses the CLI to check migration status. Cached per hook execution.
        """
        if not container_connectivity(self, CONTAINER_NAME):
            return False
        if not self._database.is_ready():
            return False
        try:
            return self._cli.migrate_status(self._database.dsn)
        except WorkloadError as exc:
            logger.error("Failed to check migration status: %s", exc)
            return False

    @property
    def _openfga_model_id(self) -> str:
        """OpenFGA model ID for the current workload version."""
        version_key = f"{OPENFGA_MODEL_ID}_{self._workload_version}"
        model_data = self.peer_data.get(version_key, "")
        return model_data if isinstance(model_data, str) else ""

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """Pebble layer with all available env var sources merged."""
        return self._pebble_service.render_pebble_layer(
            self._charm_config,
            self._database,
            self._openfga,
            OpenFGAModelData.load(self._openfga_model_id),
            self._sts,
            TracingConfig.load(self._tracing),
        )

    # --- Helpers ---

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        """Build resource requirements from charm config."""
        limits = {"cpu": self.model.config.get("cpu"), "memory": self.model.config.get("memory")}
        requests = {"cpu": "100m", "memory": "200Mi"}
        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)

    def _publish_info(self) -> None:
        """Publish current workload, migration, and OpenFGA info to requirers."""
        if not self.unit.is_leader():
            return

        mig_data = self.peer_data.get(MIGRATION_COMPLETED, "")
        migration_version = mig_data if isinstance(mig_data, str) else ""

        fga_env = self._openfga.get_env_vars() if self._openfga.is_ready() else {}
        openfga_store_id = fga_env.get("OPENFGA_STORE_ID", "")

        db_config = self._database.config if self._database.is_ready() else DatabaseConfig()

        self.authz_info_provider.publish_info(
            workload_version=self._workload_version,
            migration_version=migration_version,
            openfga_store_id=openfga_store_id,
            openfga_model_id=self._openfga_model_id,
            db_host=db_config.host,
            db_port=db_config.port,
            db_name=db_config.dbname,
            db_user=db_config.username,
            db_password=db_config.password,
        )

    def _ensure_openfga_model(self) -> bool:
        """Ensure the OpenFGA authorization model is created and stored in peer data.

        Returns:
            True when the model ID is available (already created or just created),
            False when a prerequisite is not yet satisfied.
        """
        if not self._openfga.is_ready():
            return False
        if not self.model.relations.get(PEER_INTEGRATION_NAME):
            return False

        version_key = f"{OPENFGA_MODEL_ID}_{self._workload_version}"
        if self.peer_data.get(version_key):
            return True

        if not self.unit.is_leader():
            return False

        try:
            env_vars = self._openfga.get_env_vars()
            store_id = env_vars.get("OPENFGA_STORE_ID")
            if not store_id:
                logger.warning("OPENFGA_STORE_ID missing from OpenFGA env_vars")
                return False
            model_id = self._workload_service.create_openfga_model(store_id, env=env_vars)
            logger.info("Successfully created OpenFGA model %s for version %s", model_id, self._workload_version)

        except (CreateFgaModelError, IntegrationDataError) as exc:
            logger.exception("Failed to create OpenFGA model: %s", exc)
            return False

        self.peer_data[version_key] = model_id
        return True

    # --- Event handlers ---

    def _on_holistic_handler(self, event: ops.HookEvent) -> None:
        """Apply workload configuration when all prerequisites are satisfied.

        Args:
            event: The triggering hook event.
        """
        if self.unit.is_leader() and self.istio_ingress.requirer.is_ready():
            self.istio_ingress.submit_routes()

        if not container_connectivity(self, CONTAINER_NAME):
            return
        if not self._database.is_ready():
            return

        # Phase 1: Database Migration Check & Publish
        if self.unit.is_leader() and self._migration_pending:
            try:
                self._cli.run_migration(self._database.dsn)
            except WorkloadError as exc:
                logger.error("Failed to run database migration: %s", exc)
                return
            self.peer_data[MIGRATION_COMPLETED] = self._workload_service.version
            self.__dict__.pop("_migration_pending", None)
        elif self._migration_pending:
            return

        if self.peer_data.get(MIGRATION_COMPLETED):
            self._publish_info()

        # Phase 2: OpenFGA Model/Store Check & Publish
        if not self._openfga.is_ready():
            return
        if not self._ensure_openfga_model():
            return

        self._publish_info()

        # Phase 3: Workload Container Planning
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
        logger.info("Ingress ready: %s", external_url)
        self._on_holistic_handler(event)

    def _on_run_migration_action(self, event: ops.ActionEvent) -> None:
        """Run database migrations (leader unit only).

        Args:
            event: The run-migration action event.
        """
        if not self.unit.is_leader():
            event.fail("Only the leader can run migrations")
            return

        if not container_connectivity(self, CONTAINER_NAME):
            event.fail("Container is not ready")
            return

        if not self._database.is_ready():
            event.fail("Database integration is not ready")
            return

        try:
            self._cli.run_migration(self._database.dsn)
        except WorkloadError as exc:
            event.fail(str(exc))
            return

        # Writing to peer data triggers peer_relation_changed on all units,
        # allowing non-leader units to re-evaluate and proceed via the holistic handler.
        self.peer_data[MIGRATION_COMPLETED] = self._workload_service.version
        self.__dict__.pop("_migration_pending", None)
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

        if not container_connectivity(self, CONTAINER_NAME):
            event.add_status(ops.WaitingStatus("Waiting for container"))

        if not self.model.relations.get(PEER_INTEGRATION_NAME):
            event.add_status(ops.WaitingStatus("Waiting for peer integration"))

        if not self.model.relations.get(PG_DATABASE_INTEGRATION_NAME):
            event.add_status(
                ops.BlockedStatus(f"Missing required relation: {PG_DATABASE_INTEGRATION_NAME}")
            )

        if not self._database.is_ready():
            event.add_status(ops.WaitingStatus("Waiting for database credentials"))

        if self._migration_pending:
            event.add_status(ops.BlockedStatus("Waiting for database migration"))

        if not self.model.relations.get(OPENFGA_INTEGRATION_NAME):
            event.add_status(
                ops.BlockedStatus(f"Missing required relation: {OPENFGA_INTEGRATION_NAME}")
            )

        if not self._openfga.is_ready():
            event.add_status(ops.WaitingStatus("OpenFGA store is not ready yet"))

        if not self._workload_service.is_running():
            event.add_status(ops.WaitingStatus("Waiting for workload to start"))

        event.add_status(ops.ActiveStatus())


if __name__ == "__main__":
    ops.main(AuthorizationServiceCharm)
