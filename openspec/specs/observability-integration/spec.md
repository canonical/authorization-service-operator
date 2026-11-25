## Purpose

This capability governs how the Authorization Service integrates with the Canonical Observability Stack (COS). It covers Prometheus metrics scraping, log forwarding to Loki, Grafana dashboard publishing, and distributed tracing via Tempo. All four integrations are optional — their absence does not affect the unit status — but when present they enrich the operator's visibility into the workload.

## ADDED Requirements

### Requirement: Charm exposes Prometheus scraping metrics via metrics-endpoint relation
The charm SHALL provide a `metrics-endpoint` relation (interface: `prometheus_scrape`, provider: `prometheus-k8s`) utilizing `MetricsRelationHandler` from `authorization-service-operator-shared`.

#### Scenario: Metrics handler configures Pebble environment and scrape target
- **WHEN** `MetricsRelationHandler` is initialized and passed to `render_pebble_layer`
- **THEN** `MetricsRelationHandler` registers the unit's scrape target on port `9100` and path `/metrics` along with Prometheus alert rules from `src/prometheus_alert_rules/`
- **AND** `METRICS_ENABLED=true`, `METRICS_PORT=9100`, and `METRICS_PATH=/metrics` are added to the Pebble environment

### Requirement: Charm forwards logs to Loki via logging relation
The charm SHALL consume the `logging` relation endpoint (interface: `loki_k8s.v1.loki_push_api`, provider: `loki-k8s`).

#### Scenario: Loki relation is established
- **WHEN** the `logging` relation is joined and the Loki endpoint is available
- **THEN** the charm configures the workload to forward logs to the provided Loki push URL and publishes Loki alert rules from `src/loki_alert_rules/`

#### Scenario: Loki relation is absent
- **WHEN** no `logging` relation is present
- **THEN** the charm continues to operate and logs are emitted locally only

### Requirement: Charm provides a Grafana dashboard via relation
The charm SHALL provide a `grafana-dashboard` relation endpoint (interface: `grafana_dashboard`, provider: `grafana-k8s`).

#### Scenario: Grafana relation is established
- **WHEN** the `grafana-dashboard` relation is joined
- **THEN** the charm publishes the dashboard JSON to the relation databag

### Requirement: Charm enables distributed tracing when the tracing relation is joined
The charm SHALL consume the `tracing` relation (interface: `tempo_coordinator_k8s.v0.tracing`, provider: `tempo-coordinator-k8s`) requesting the `otlp_grpc` protocol. When joined and ready, `TELEMETRY_ENABLED` SHALL be set to `true` and `OTEL_EXPORTER_OTLP_ENDPOINT` SHALL be set from the `otlp_grpc` relation data. `OTEL_SERVICE_NAME` is always `authorization-service` (static via `DEFAULT_CONTAINER_ENV`). When the relation is absent, `TELEMETRY_ENABLED` defaults to `false`.

#### Scenario: Tracing relation is established
- **WHEN** the `tracing` relation is joined and the provider publishes an `otlp_grpc` endpoint
- **THEN** `TracingConfig.to_env_vars()` returns `TELEMETRY_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=<endpoint>`
- **AND** `_on_holistic_handler()` re-applies the Pebble layer with the updated env vars

#### Scenario: Tracing relation is absent
- **WHEN** no `tracing` relation is present
- **THEN** `TELEMETRY_ENABLED=false` (from `DEFAULT_CONTAINER_ENV`)
- **AND** the unit does NOT enter `BlockedStatus`

#### Scenario: Tracing relation is removed
- **WHEN** the `tracing` relation is broken
- **THEN** `TELEMETRY_ENABLED` reverts to `false` after `_on_holistic_handler()` re-applies the layer
