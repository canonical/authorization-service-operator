# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""String constants for the Authorization Service charm."""

from string import Template

CONTAINER_NAME = "authorization-service"
SERVICE_NAME = "authorization-service"
PEBBLE_CHECK_NAME = "ready"
APP_BINARY = "/usr/bin/app"

# Integrations
PG_DATABASE_INTEGRATION_NAME = "pg-database"
POSTGRESQL_DSN_TEMPLATE = Template("postgres://$username:$password@$endpoint/$database")
OPENFGA_INTEGRATION_NAME = "openfga"
OPENFGA_STORE_NAME = "authorization-service-store"
TRACING_INTEGRATION_NAME = "tracing"
INGRESS_INTEGRATION_NAME = "ingress"
GRAFANA_DASHBOARD_INTEGRATION_NAME = "grafana-dashboard"
LOGGING_INTEGRATION_NAME = "logging"
STS_INFO_INTEGRATION_NAME = "sts-info"
FORWARD_AUTH_INTEGRATION_NAME = "forward-auth"
PEER_INTEGRATION_NAME = "authorization-service-peers"

# Ports
GRPC_PORT = 9091
HTTP_PORT = 8070
INGRESS_HTTP_PORT = 80
INGRESS_HTTPS_PORT = 443

# Peer integration data keys
MIGRATION_COMPLETED = "migration_completed"
OPENFGA_MODEL_ID = "openfga_model_id"
