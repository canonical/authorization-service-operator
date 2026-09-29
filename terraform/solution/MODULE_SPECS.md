<!-- BEGIN_TF_DOCS -->

---
## Providers

| Name | Version |
| ---- | ------- |
| <a name="provider_juju"></a> [juju](#provider\_juju) | >= 1.0 |
---
## Requirements

| Name | Version |
| ---- | ------- |
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.6 |
| <a name="requirement_juju"></a> [juju](#requirement\_juju) | >= 1.0 |
---
## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| <a name="input_model"></a> [model](#input\_model) | The UUID of the Juju model to deploy the Authorization Service into. | `string` | n/a | yes |
| <a name="input_postgresql_offer_url"></a> [postgresql\_offer\_url](#input\_postgresql\_offer\_url) | PostgreSQL Juju Offer URL (cross-model DB endpoint) | `string` | n/a | yes |
| <a name="input_openfga_offer_url"></a> [openfga\_offer\_url](#input\_openfga\_offer\_url) | OpenFGA Juju Offer URL (cross-model OpenFGA endpoint) | `string` | n/a | yes |
| <a name="input_ingress_offer_url"></a> [ingress\_offer\_url](#input\_ingress\_offer\_url) | Ingress Juju Offer URL (cross-model Ingress endpoint) | `string` | `null` | no |
| <a name="input_kafka_offer_url"></a> [kafka\_offer\_url](#input\_kafka\_offer\_url) | Kafka Juju Offer URL (cross-model Kafka endpoint for listener) | `string` | n/a | yes |
| <a name="input_sts_info_offer_url"></a> [sts\_info\_offer\_url](#input\_sts\_info\_offer\_url) | STS Info Juju Offer URL (cross-model STS endpoint) | `string` | `null` | no |
| <a name="input_authorization_service"></a> [authorization\_service](#input\_authorization\_service) | The configuration of the Authorization Service application. | <pre>object({<br/>    name        = optional(string, "authorization-service")<br/>    units       = optional(number, 1)<br/>    channel     = optional(string, "latest/stable")<br/>    base        = optional(string, null)<br/>    trust       = optional(bool, true)<br/>    config      = optional(map(string), {})<br/>    constraints = optional(string, null)<br/>    revision    = optional(number, null)<br/>    resources   = optional(map(string), {})<br/>  })</pre> | `{}` | no |
| <a name="input_authorization_service_worker"></a> [authorization\_service\_worker](#input\_authorization\_service\_worker) | The configuration of the Authorization Service Worker application. | <pre>object({<br/>    name        = optional(string, "authorization-service-worker")<br/>    units       = optional(number, 1)<br/>    channel     = optional(string, "latest/stable")<br/>    base        = optional(string, null)<br/>    trust       = optional(bool, true)<br/>    config      = optional(map(string), {})<br/>    constraints = optional(string, null)<br/>    revision    = optional(number, null)<br/>    resources   = optional(map(string), {})<br/>  })</pre> | `{}` | no |
| <a name="input_authorization_service_listener"></a> [authorization\_service\_listener](#input\_authorization\_service\_listener) | The configuration of the Authorization Service Listener application. | <pre>object({<br/>    name        = optional(string, "authorization-service-listener")<br/>    units       = optional(number, 1)<br/>    channel     = optional(string, "latest/stable")<br/>    base        = optional(string, null)<br/>    trust       = optional(bool, true)<br/>    config      = optional(map(string), {})<br/>    constraints = optional(string, null)<br/>    revision    = optional(number, null)<br/>    resources   = optional(map(string), {})<br/>  })</pre> | `{}` | no |
| <a name="input_metrics_offer_url"></a> [metrics\_offer\_url](#input\_metrics\_offer\_url) | Optional Metrics Offer URL for COS integration | `string` | `null` | no |
| <a name="input_tracing_offer_url"></a> [tracing\_offer\_url](#input\_tracing\_offer\_url) | Optional Tracing Offer URL for COS integration | `string` | `null` | no |
| <a name="input_logging_offer_url"></a> [logging\_offer\_url](#input\_logging\_offer\_url) | Optional Logging Offer URL for COS integration | `string` | `null` | no |
| <a name="input_grafana_dashboard_offer_url"></a> [grafana\_dashboard\_offer\_url](#input\_grafana\_dashboard\_offer\_url) | Optional Grafana Dashboard Offer URL for COS integration | `string` | `null` | no |
---
## Outputs

| Name | Description |
| ---- | ----------- |
| <a name="output_authorization_service_app_name"></a> [authorization\_service\_app\_name](#output\_authorization\_service\_app\_name) | The name of the deployed Authorization Service application |
| <a name="output_authorization_service_worker_app_name"></a> [authorization\_service\_worker\_app\_name](#output\_authorization\_service\_worker\_app\_name) | The name of the deployed Authorization Service Worker application |
| <a name="output_authorization_service_listener_app_name"></a> [authorization\_service\_listener\_app\_name](#output\_authorization\_service\_listener\_app\_name) | The name of the deployed Authorization Service Listener application |
| <a name="output_forward_auth_offer_url"></a> [forward\_auth\_offer\_url](#output\_forward\_auth\_offer\_url) | The Juju offer URL for Forward Auth |
| <a name="output_authorization_service_info_offer_url"></a> [authorization\_service\_info\_offer\_url](#output\_authorization\_service\_info\_offer\_url) | The Juju offer URL for Authorization Service Info |
<!-- END_TF_DOCS -->