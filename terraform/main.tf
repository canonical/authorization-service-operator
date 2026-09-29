# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

/**
 * # Terraform module for the authorization-service charm
 *
 * This is a Terraform module facilitating the deployment of the authorization-service
 * charm using the Juju Terraform provider.
 */

resource "juju_application" "authorization_service" {
  name        = var.app_name
  model_uuid  = var.model_uuid
  config      = var.config
  constraints = var.constraints
  resources   = var.resources
  units       = var.units
  trust       = true

  charm {
    name     = "authorization-service"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}

resource "juju_offer" "forward_auth" {
  name             = "forward-auth"
  model_uuid       = var.model_uuid
  application_name = juju_application.authorization_service.name
  endpoints        = ["forward-auth"]
}

resource "juju_offer" "authorization_service_info" {
  name             = "authorization-service-info"
  model_uuid       = var.model_uuid
  application_name = juju_application.authorization_service.name
  endpoints        = ["authorization-service-info"]
}
