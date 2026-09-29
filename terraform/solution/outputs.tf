# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "authorization_service_app_name" {
  description = "The name of the deployed Authorization Service application"
  value       = module.authorization_service.application.name
}

output "authorization_service_worker_app_name" {
  description = "The name of the deployed Authorization Service Worker application"
  value       = module.authorization_service_worker.application.name
}

output "authorization_service_listener_app_name" {
  description = "The name of the deployed Authorization Service Listener application"
  value       = module.authorization_service_listener.application.name
}

output "forward_auth_offer_url" {
  description = "The Juju offer URL for Forward Auth"
  value       = module.authorization_service.offers.forward-auth.url
}

output "authorization_service_info_offer_url" {
  description = "The Juju offer URL for Authorization Service Info"
  value       = module.authorization_service.offers.authorization-service-info.url
}
