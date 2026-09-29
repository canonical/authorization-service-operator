# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Local info integration between authorization-service and worker
resource "juju_integration" "worker_info" {
  application {
    name     = module.authorization_service.application.name
    endpoint = "authorization-service-info"
  }

  application {
    name     = module.authorization_service_worker.application.name
    endpoint = "authorization-service-info"
  }

  model_uuid = data.juju_model.this.uuid
}

# Local info integration between authorization-service and listener
resource "juju_integration" "listener_info" {
  application {
    name     = module.authorization_service.application.name
    endpoint = "authorization-service-info"
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "authorization-service-info"
  }

  model_uuid = data.juju_model.this.uuid
}

# Database cross-model integration for server
resource "juju_integration" "database" {
  application {
    offer_url = data.juju_offer.database.url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "pg-database"
  }

  model_uuid = data.juju_model.this.uuid
}

# OpenFGA cross-model integration for server
resource "juju_integration" "openfga" {
  application {
    offer_url = data.juju_offer.openfga.url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "openfga"
  }

  model_uuid = data.juju_model.this.uuid
}

# OpenFGA cross-model integration for worker
resource "juju_integration" "openfga_worker" {
  application {
    offer_url = data.juju_offer.openfga.url
  }

  application {
    name     = module.authorization_service_worker.application.name
    endpoint = "openfga"
  }

  model_uuid = data.juju_model.this.uuid
}

# Ingress cross-model integration for server
resource "juju_integration" "ingress" {
  count = var.ingress_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.ingress[0].url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "ingress"
  }

  model_uuid = data.juju_model.this.uuid
}

# STS info cross-model integration for server
resource "juju_integration" "sts_info" {
  count = var.sts_info_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.sts_info[0].url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "sts-info"
  }

  model_uuid = data.juju_model.this.uuid
}

# Kafka cross-model integration for listener
resource "juju_integration" "kafka" {
  application {
    offer_url = data.juju_offer.kafka.url
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "kafka"
  }

  model_uuid = data.juju_model.this.uuid
}

# Optional COS integrations for Server
resource "juju_integration" "tracing" {
  count = var.tracing_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.tracing[0].url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "tracing"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "logging" {
  count = var.logging_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.logging[0].url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "logging"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "grafana_dashboard" {
  count = var.grafana_dashboard_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.grafana_dashboard[0].url
  }

  application {
    name     = module.authorization_service.application.name
    endpoint = "grafana-dashboard"
  }

  model_uuid = data.juju_model.this.uuid
}

# Optional COS integrations for Worker
resource "juju_integration" "metrics_worker" {
  count = var.metrics_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.metrics[0].url
  }

  application {
    name     = module.authorization_service_worker.application.name
    endpoint = "metrics-endpoint"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "grafana_dashboard_worker" {
  count = var.grafana_dashboard_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.grafana_dashboard[0].url
  }

  application {
    name     = module.authorization_service_worker.application.name
    endpoint = "grafana-dashboard"
  }

  model_uuid = data.juju_model.this.uuid
}

# Optional COS integrations for Listener
resource "juju_integration" "metrics_listener" {
  count = var.metrics_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.metrics[0].url
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "metrics-endpoint"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "tracing_listener" {
  count = var.tracing_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.tracing[0].url
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "tracing"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "logging_listener" {
  count = var.logging_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.logging[0].url
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "logging"
  }

  model_uuid = data.juju_model.this.uuid
}

resource "juju_integration" "grafana_dashboard_listener" {
  count = var.grafana_dashboard_offer_url != null ? 1 : 0

  application {
    offer_url = data.juju_offer.grafana_dashboard[0].url
  }

  application {
    name     = module.authorization_service_listener.application.name
    endpoint = "grafana-dashboard"
  }

  model_uuid = data.juju_model.this.uuid
}
