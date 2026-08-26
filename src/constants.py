# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""String constants for the Authorization Service charm."""


CONTAINER_NAME = "authorization-service"

# Integrations
PG_DATABASE_INTEGRATION_NAME = "pg-database"
OPENFGA_INTEGRATION_NAME = "openfga"
TRACING_INTEGRATION_NAME = "tracing"
INGRESS_INTEGRATION_NAME = "ingress"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
LOGGING_INTEGRATION_NAME = "logging"
STS_INFO_INTEGRATION_NAME = "sts-info"
FORWARD_AUTH_INTEGRATION_NAME = "forward-auth"
PEER_INTEGRATION_NAME = "authorization-service-peers"
AUTHORIZATION_SERVICE_INFO_INTEGRATION_NAME = "authorization-service-info"

# Ports
GRPC_PORT = 9091
INGRESS_HTTP_PORT = 80
INGRESS_HTTPS_PORT = 443

# Peer integration data keys
MIGRATION_COMPLETED = "migration_completed"
OPENFGA_MODEL_ID = "openfga_model_id"
