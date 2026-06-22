## Purpose

This capability governs the full lifecycle of the `authorization-service` Pebble workload — from initial start through configuration changes, upgrades, and removal. It covers the Pebble layer definition (entrypoint, health check, environment), workload version reporting, port management, and the operator-controlled database migration flow via a Juju action. OpenFGA is a required integration; its absence blocks the workload from starting.

## ADDED Requirements

### Requirement: Pebble service runs the correct entrypoint
The Pebble layer MUST define the service command as `/usr/bin/app serve`. All CLI sub-commands (`version`, `migrate`, `migrate status`) also invoke `/usr/bin/app`.

#### Scenario: Pebble layer contains the correct command
- **WHEN** `PebbleService.render_pebble_layer(*sources)` is called
- **THEN** the returned `Layer` contains service command `/usr/bin/app serve`
The charm SHALL handle the `pebble_ready` event by delegating to `_on_holistic_handler()`, which calls `PebbleService.plan(layer)` with the layer rendered by `PebbleService.render_pebble_layer(*sources)`. The charm then sets the workload version (see below). Unit status is reported via `_on_collect_status`. The layer is assembled by merging `to_env_vars()` from all active `EnvVarConvertible` sources with `DEFAULT_CONTAINER_ENV`.

#### Scenario: Service starts successfully on pebble_ready
- **WHEN** the charm receives the `pebble_ready` event and all required relations are satisfied
- **THEN** the charm pushes a Pebble layer, starts the `authorization-service` service, and sets the workload version
- **AND** `_on_collect_status` reports `ActiveStatus`

#### Scenario: Required relation not yet available on pebble_ready
- **WHEN** `pebble_ready` fires but a required relation (e.g., database) is not yet satisfied
- **THEN** `_on_collect_status` reports `BlockedStatus("Waiting for <relation>")`
- **AND** the service is NOT started

### Requirement: Workload version is reported on pebble_ready
The charm SHALL call `WorkloadService.update_workload_version()` immediately after the service starts on `pebble_ready`. Internally, this delegates to `CommandLine.get_service_version()`, which runs `/usr/bin/app version` via Pebble exec and returns its stdout as a string; the result is passed to `self.unit.set_workload_version()`.

#### Scenario: Version is set after successful start
- **WHEN** `pebble_ready` fires and the service starts successfully
- **THEN** the charm calls `WorkloadService.update_workload_version()` and sets the workload version on the unit
- **AND** `_on_collect_status` reports `ActiveStatus`

#### Scenario: Version command fails
- **WHEN** `CommandLine.get_service_version()` raises an exception (e.g., non-zero exit code)
- **THEN** the charm logs a warning and continues without blocking
- **AND** `_on_collect_status` still reports `ActiveStatus`

### Requirement: Pebble layer is idempotently re-applied on config or relation changes
The charm SHALL call `_on_holistic_handler()` in response to `config_changed` and integration relation events (`*_created`, `*_changed`, `*_broken`). `PebbleService.plan(layer)` SHALL only restart the service if the rendered plan differs from the current plan.

#### Scenario: Config change triggers workload reconfigure
- **WHEN** a `config_changed` event is received with a new `log_level` value
- **THEN** the charm updates the Pebble layer environment variables and restarts the `authorization-service` service

#### Scenario: Relation data change triggers workload reconfigure
- **WHEN** a database `endpoints_changed` event is received with new connection details
- **THEN** the charm re-applies the Pebble layer with the updated DSN environment variable and restarts the service

### Requirement: Database migration is triggered by the operator via a Juju action
The charm SHALL NOT run database migration automatically. On `upgrade_charm`, the charm SHALL call `/usr/bin/app migrate status` to check whether migration is pending. If migration is needed, the charm SHALL report `WaitingStatus("Waiting for database migration")` via `_on_collect_status` — the workload SHALL NOT be started or reconfigured until migration is complete.

The operator triggers migration by running `juju run <unit> run-migration`. The `run-migration` action handler is leader-only; it calls `CommandLine.run_migration(dsn)` where `dsn` is constructed via `POSTGRESQL_DSN_TEMPLATE` from `DatabaseConfig`. The CLI command is `/usr/bin/app migrate --dsn <dsn>`. On success it stores the current workload version in peer data under `MIGRATION_COMPLETED` and calls `_on_holistic_handler()`.

#### Scenario: Upgrade detects pending migration
- **WHEN** the `upgrade_charm` event fires and `/usr/bin/app migrate status` indicates migration is needed
- **THEN** `_on_collect_status` reports `WaitingStatus("Waiting for database migration")`
- **AND** `_on_holistic_handler()` is NOT called

#### Scenario: Upgrade detects no migration needed
- **WHEN** the `upgrade_charm` event fires and `/usr/bin/app migrate status` indicates no migration is pending
- **THEN** `_on_holistic_handler()` is called directly
- **AND** `_on_collect_status` reports `ActiveStatus`

#### Scenario: Operator runs run-migration action on leader
- **WHEN** the operator runs `juju run <unit> run-migration` on the leader unit
- **THEN** `CommandLine.run_migration(dsn)` is called with the PostgreSQL DSN
- **AND** on success, the workload version is stored in peer data and `_on_holistic_handler()` runs
- **AND** `_on_collect_status` reports `ActiveStatus`

#### Scenario: Operator runs run-migration action on non-leader
- **WHEN** the operator runs `juju run <non-leader-unit> run-migration`
- **THEN** the action fails with a message indicating only the leader can run migrations

#### Scenario: Migration action fails
- **WHEN** `CommandLine.run_migration(dsn)` raises `WorkloadError`
- **THEN** the action fails with the error message

### Requirement: Pebble health check is defined in the service layer and managed by Pebble
The `PEBBLE_LAYER_DICT` constant in `src/services.py` SHALL include a Pebble `http` check named `"ready"` with `on-check-failure: restart`. This check is a **Pebble-managed** background concern — it drives automatic service restarts but does NOT gate the charm's `ActiveStatus`. The charm sets `ActiveStatus` based on successful event handling, not by polling the check.

#### Scenario: Health check is present in the layer definition
- **WHEN** `PebbleService.render_pebble_layer(*sources)` is called
- **THEN** the returned `Layer` contains an `http` check named `"ready"` targeting `http://localhost:8070/healthz`
- **AND** `on-check-failure` is set to `restart`

### Requirement: Both HTTP and gRPC ports are opened on the unit
The charm SHALL call `WorkloadService.open_port()` to open both `HTTP_PORT` (8070) and `GRPC_PORT` (9091) on the unit. This allows Kubernetes network policies to permit REST API and direct gRPC traffic respectively. No Juju relation endpoint is exposed for gRPC.

#### Scenario: Ports are opened after successful start
- **WHEN** the service starts successfully on `pebble_ready`
- **THEN** the charm opens port `8070` (TCP) and port `9091` (TCP) on the unit

### Requirement: Workload requires OpenFGA integration to start
The charm SHALL block when the `openfga` relation (interface: `openfga_k8s.v1.openfga`, provider: `openfga-k8s`) is absent, as the Authorization Service cannot function without its policy engine. When joined, `OpenFGAConfig.to_env_vars()` SHALL supply `OPENFGA_ADDRESS`, `OPENFGA_STORE_ID`, `OPENFGA_AUTHZ_MODEL_ID`, and `OPENFGA_API_KEY`.

#### Scenario: OpenFGA relation is absent
- **WHEN** the unit starts and no `openfga` relation is joined
- **THEN** `_on_collect_status` reports `BlockedStatus("Waiting for openfga relation")`
- **AND** the Pebble service is NOT started

#### Scenario: OpenFGA relation provides all required fields
- **WHEN** the `openfga` relation is joined with store ID, model ID, API key, and address
- **THEN** `OpenFGAConfig.to_env_vars()` returns the four `OPENFGA_*` env vars
- **AND** `_on_holistic_handler()` re-applies the Pebble layer

#### Scenario: OpenFGA relation is removed
- **WHEN** the `openfga` `relation_broken` event fires
- **THEN** `PebbleService.stop()` is called
- **AND** `_on_collect_status` reports `BlockedStatus("openfga relation removed")`

