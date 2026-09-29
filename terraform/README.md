# Terraform Modules for Charmed Authorization Service

This directory contains Terraform modules to easily deploy, configure, and manage Charmed Authorization Service and its dependencies on Kubernetes using Juju.

---

## Module Directory Structure

Our Terraform integrations are designed in two distinct layers:

1. **[Core Module](./)** (this folder):
   Deploys only the core `authorization-service` application itself into an existing Juju model.
2. **[Solution Module](./solution/)**:
   A composite solution module that deploys the entire Authorization Service suite (`authorization-service`, `authorization-service-worker`, and `authorization-service-listener`) and integrates them with database (PostgreSQL), OpenFGA, ingress, Kafka, and observability dependencies.

---

## Core Module Configuration (`terraform`)

To deploy only the `authorization-service` application itself, declare it like this:

```hcl
module "authorization_service" {
  source = "github.com/canonical/authorization-service-operator//terraform"

  model_uuid = var.model_uuid
  app_name   = "authorization-service"
  channel    = "latest/stable"
  units      = 1
}
```

For a full list of configuration options, variables, and schema attributes, refer to the generated specifications:
* [Core Module Specs](./MODULE_SPECS.md)

---

## Solution Module Configuration (`terraform/solution`)

To consume the `solution` module directly within your own infrastructure code, declare it like this:

```hcl
module "authorization_service_stack" {
  source = "github.com/canonical/authorization-service-operator//terraform/solution"

  model                = var.my_model_uuid
  postgresql_offer_url = "admin/core.postgresql-k8s"
  openfga_offer_url    = "admin/core.openfga-k8s"
  kafka_offer_url      = "admin/core.kafka-k8s"

  # Optional Ingress and STS integrations
  ingress_offer_url  = "admin/core.traefik-public"
  sts_info_offer_url = "admin/core.sts"

  # Optional Observability Integrations
  metrics_offer_url           = "admin/cos.prometheus"
  logging_offer_url           = "admin/cos.loki"
  tracing_offer_url           = "admin/cos.tempo"
  grafana_dashboard_offer_url = "admin/cos.grafana"
}
```

### Core Inputs

| Name | Description | Type | Required |
|------|-------------|------|:--------:|
| `model` | UUID of the Juju model to deploy the Authorization Service suite into | `string` | **Yes** |
| `postgresql_offer_url` | Offer URL of the PostgreSQL database application | `string` | **Yes** |
| `openfga_offer_url` | Offer URL of the OpenFGA application | `string` | **Yes** |
| `kafka_offer_url` | Offer URL of the Kafka cluster (required for listener) | `string` | **Yes** |
| `ingress_offer_url` | Offer URL of the Ingress route controller | `string` | No |
| `sts_info_offer_url` | Offer URL of the STS info endpoint | `string` | No |
| `metrics_offer_url` | Offer URL of the Prometheus scrape metrics endpoint | `string` | No |
| `logging_offer_url` | Offer URL of the Loki logging endpoint | `string` | No |
| `tracing_offer_url` | Offer URL of the Tempo tracing endpoint | `string` | No |
| `grafana_dashboard_offer_url` | Offer URL of the Grafana dashboard import endpoint | `string` | No |

For a full list of configuration options, variables, and schema attributes, refer to:
* [Solution Module Specs](./solution/MODULE_SPECS.md)
