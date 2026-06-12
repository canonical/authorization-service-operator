## Purpose

This capability governs the integration with PostgreSQL via the `pg-database` relation. It ensures the workload has access to a running, credential-supplied database before it is started, propagates connection details as discrete `POSTGRES_*` environment variables, and stops the service when the database relation is removed.

## ADDED Requirements

### Requirement: Charm blocks when pg-database relation is not established
The charm SHALL report `BlockedStatus` via `_on_collect_status` when the `pg-database` relation is missing and no database credentials are available.

#### Scenario: No database relation present
- **WHEN** the unit starts and no `pg-database` relation is joined
- **THEN** `_on_collect_status` reports `BlockedStatus("Waiting for pg-database relation")`
- **AND** the Pebble service is NOT started

### Requirement: Database credentials are consumed as discrete POSTGRES_* environment variables
The charm SHALL read connection details from the `DatabaseRequires` library and expose them via `DatabaseConfig.to_env_vars()`. The env vars SHALL use the `POSTGRES_*` naming convention, not a single DSN.

| Env var | Source field |
|---|---|
| `POSTGRES_HOST` | `endpoints` host |
| `POSTGRES_PORT` | `endpoints` port |
| `POSTGRES_USER` | `username` |
| `POSTGRES_PASSWORD` | `password` |
| `POSTGRES_DB` | `database` |

#### Scenario: pg-database relation provides credentials
- **WHEN** the `database_created` or `endpoints_changed` event fires with valid connection data
- **THEN** `DatabaseConfig.to_env_vars()` returns a dict containing `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`
- **AND** `_on_holistic_handler()` is called to re-apply the Pebble layer

#### Scenario: Database relation data is incomplete
- **WHEN** the `pg-database` relation is joined but credentials are not yet available
- **THEN** `_on_collect_status` reports `WaitingStatus("Waiting for database credentials")`
- **AND** the Pebble service is NOT (re)started

### Requirement: Database relation teardown blocks the workload
The charm SHALL stop the service and report `BlockedStatus` when the `pg-database` relation is removed.

#### Scenario: Database relation is removed
- **WHEN** the `relation_broken` event fires for the `pg-database` relation
- **THEN** `PebbleService.stop()` is called
- **AND** `_on_collect_status` reports `BlockedStatus("Waiting for pg-database relation")`
