# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variable "model" {
  description = "The UUID of the Juju model to deploy the Authorization Service into."
  type        = string
}

variable "postgresql_offer_url" {
  description = "PostgreSQL Juju Offer URL (cross-model DB endpoint)"
  type        = string
}

variable "openfga_offer_url" {
  description = "OpenFGA Juju Offer URL (cross-model OpenFGA endpoint)"
  type        = string
}

variable "ingress_offer_url" {
  description = "Ingress Juju Offer URL (cross-model Ingress endpoint)"
  type        = string
  default     = null
}

variable "kafka_offer_url" {
  description = "Kafka Juju Offer URL (cross-model Kafka endpoint for listener)"
  type        = string
}

variable "sts_info_offer_url" {
  description = "STS Info Juju Offer URL (cross-model STS endpoint)"
  type        = string
  default     = null
}

variable "authorization_service" {
  description = "The configuration of the Authorization Service application."
  type = object({
    name        = optional(string, "authorization-service")
    units       = optional(number, 1)
    channel     = optional(string, "latest/stable")
    base        = optional(string, null)
    trust       = optional(bool, true)
    config      = optional(map(string), {})
    constraints = optional(string, null)
    revision    = optional(number, null)
    resources   = optional(map(string), {})
  })
  default = {}
}

variable "authorization_service_worker" {
  description = "The configuration of the Authorization Service Worker application."
  type = object({
    name        = optional(string, "authorization-service-worker")
    units       = optional(number, 1)
    channel     = optional(string, "latest/stable")
    base        = optional(string, null)
    trust       = optional(bool, true)
    config      = optional(map(string), {})
    constraints = optional(string, null)
    revision    = optional(number, null)
    resources   = optional(map(string), {})
  })
  default = {}
}

variable "authorization_service_listener" {
  description = "The configuration of the Authorization Service Listener application."
  type = object({
    name        = optional(string, "authorization-service-listener")
    units       = optional(number, 1)
    channel     = optional(string, "latest/stable")
    base        = optional(string, null)
    trust       = optional(bool, true)
    config      = optional(map(string), {})
    constraints = optional(string, null)
    revision    = optional(number, null)
    resources   = optional(map(string), {})
  })
  default = {}
}

variable "metrics_offer_url" {
  description = "Optional Metrics Offer URL for COS integration"
  type        = string
  default     = null
}

variable "tracing_offer_url" {
  description = "Optional Tracing Offer URL for COS integration"
  type        = string
  default     = null
}

variable "logging_offer_url" {
  description = "Optional Logging Offer URL for COS integration"
  type        = string
  default     = null
}

variable "grafana_dashboard_offer_url" {
  description = "Optional Grafana Dashboard Offer URL for COS integration"
  type        = string
  default     = null
}
