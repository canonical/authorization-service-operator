## Purpose

This capability governs how the Authorization Service integrates with the Canonical Observability Stack (COS). It covers log forwarding to Loki, Grafana dashboard publishing, and distributed tracing via Tempo. All three integrations are optional — their absence does not affect the unit status — but when present they enrich the operator's visibility into the workload.

## ADDED Requirements

### Requirement: Charm forwards logs to Loki via push-api relation
The charm SHALL provide a `loki_push_api` relation endpoint (interface: `loki_k8s.v1.loki_push_api`, provider: `loki-k8s`).

#### Scenario: Loki relation is established
- **WHEN** the `loki_push_api` relation is joined and the Loki endpoint is available
- **THEN** the charm configures the workload to forward logs to the provided Loki push URL

#### Scenario: Loki relation is absent
- **WHEN** no `loki_push_api` relation is present
- **THEN** the charm continues to operate and logs are emitted locally only

### Requirement: Charm provides a Grafana dashboard via relation
The charm SHALL provide a `grafana_dashboard` relation endpoint (interface: `grafana_dashboard`, provider: `grafana-k8s`).

#### Scenario: Grafana relation is established
- **WHEN** the `grafana_dashboard` relation is joined
- **THEN** the charm publishes the dashboard JSON to the relation databag

### Requirement: Charm enables distributed tracing when the tracing relation is joined
The charm SHALL consume the `tracing` relation (interface: `tempo_coordinator_k8s.v0.tracing`, provider: `tempo-coordinator-k8s`). When joined, `TELEMETRY_ENABLED` SHALL be set to `true` and `OTEL_EXPORTER_OTLP_ENDPOINT` SHALL be set from the relation data. `OTEL_SERVICE_NAME` is always `authorization-service` (static via `DEFAULT_CONTAINER_ENV`). When the relation is absent, `TELEMETRY_ENABLED` defaults to `false`.

#### Scenario: Tracing relation is established
- **WHEN** the `tracing` relation is joined and the provider publishes an OTLP endpoint
- **THEN** `TracingConfig.to_env_vars()` returns `TELEMETRY_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=<endpoint>`
- **AND** `_on_holistic_handler()` re-applies the Pebble layer with the updated env vars

#### Scenario: Tracing relation is absent
- **WHEN** no `tracing` relation is present
- **THEN** `TELEMETRY_ENABLED=false` (from `DEFAULT_CONTAINER_ENV`)
- **AND** the unit does NOT enter `BlockedStatus`

#### Scenario: Tracing relation is removed
- **WHEN** the `tracing` relation is broken
- **THEN** `TELEMETRY_ENABLED` reverts to `false` after `_on_holistic_handler()` re-applies the layer
