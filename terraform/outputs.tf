# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "The deployed juju_application resource"
  value       = juju_application.authorization_service
}

output "provides" {
  description = "Map of provides endpoint names"
  value = {
    authorization-service-info = "authorization-service-info"
    forward-auth               = "forward-auth"
    grafana-dashboard          = "grafana-dashboard"
    logging                    = "logging"
  }
}

output "requires" {
  description = "Map of requires endpoint names"
  value = {
    ingress     = "ingress"
    openfga     = "openfga"
    pg-database = "pg-database"
    sts-info    = "sts-info"
    tracing     = "tracing"
  }
}

output "offers" {
  description = "The Juju offers that the charm provides"
  value = {
    authorization-service-info = juju_offer.authorization_service_info
    forward-auth               = juju_offer.forward_auth
  }
}
