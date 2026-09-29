# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

module "authorization_service" {
  source = "../"

  model_uuid  = data.juju_model.this.uuid
  app_name    = var.authorization_service.name
  units       = var.authorization_service.units
  channel     = var.authorization_service.channel
  base        = var.authorization_service.base
  config      = var.authorization_service.config
  constraints = var.authorization_service.constraints
  revision    = var.authorization_service.revision
  resources   = var.authorization_service.resources
}

module "authorization_service_worker" {
  source = "github.com/canonical/authorization-service-worker-operator//terraform"

  model_uuid  = data.juju_model.this.uuid
  app_name    = var.authorization_service_worker.name
  units       = var.authorization_service_worker.units
  channel     = var.authorization_service_worker.channel
  base        = var.authorization_service_worker.base
  config      = var.authorization_service_worker.config
  constraints = var.authorization_service_worker.constraints
  revision    = var.authorization_service_worker.revision
  resources   = var.authorization_service_worker.resources
}

module "authorization_service_listener" {
  source = "github.com/canonical/authorization-service-listener-operator//terraform"

  model_uuid  = data.juju_model.this.uuid
  app_name    = var.authorization_service_listener.name
  units       = var.authorization_service_listener.units
  channel     = var.authorization_service_listener.channel
  base        = var.authorization_service_listener.base
  config      = var.authorization_service_listener.config
  constraints = var.authorization_service_listener.constraints
  revision    = var.authorization_service_listener.revision
  resources   = var.authorization_service_listener.resources
}
