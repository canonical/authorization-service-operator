## Context

The Authorization Service (Cerberus) is a Policy Decision Point in the Canonical centralized identity platform. It is a Kubernetes workload delivered as an OCI image (`ghcr.io/canonical/authorization-service:v0.2.0`).
This change implements the Charmed Operator that manages its full lifecycle — from initial deployment through configuration, integration, and observability — using the Canonical Juju Python Ops SDK.

> **Architecture note**: This charm operates as the **server** in the server–consumer architecture of the Canonical identity platform. It exposes policy decision endpoints consumed by other services (OAuth2 Proxy, downstream applications). It is a pure requirer/consumer of all integrations it depends on (PostgreSQL, OpenFGA, STS, ingress).

## Workload Configuration

The Charmed Authorization Service Operator injects and manages the following environment variables within the workload container:

### Server Configuration

| Environment Variable | Type | Source                       | Details |
| :--- | :--- |:-----------------------------| :--- |
| `GRPC_PORT` | `int` | Charm (static)               | Required; value: `9091` |
| `HTTP_PORT` | `int` | Charm (static)               | Required; value: `8070` |
| `DEV` | `bool` | Charm Config (`dev`)         | Default: `false`. Enables development mode. |
| `HTTP_PROXY` | `string` | Charm Config (`http_proxy`)  | URL of the HTTP proxy, e.g., `http://proxy.internal:6666` |
| `HTTPS_PROXY` | `string` | Charm Config (`https_proxy`) | URL of the HTTPS proxy, e.g., `https://proxy.internal:6666` |
| `NO_PROXY` | `string` | Charm Config (`no_proxy`)    | Domains excluded from proxying, e.g., `test.com,test.co.uk` (comma-separated list). |

### OpenFGA Configuration

| Environment Variable | Type | Source | Details |
| :--- | :--- | :--- | :--- |
| `OPENFGA_ADDRESS` | `string` | Integration (`openfga`) | Required. Default: `http://localhost:8081`. Address of the OpenFGA service. |
| `OPENFGA_STORE_ID` | `string` | Integration (`openfga`) | Required. OpenFGA Store ID. |
| `OPENFGA_AUTHZ_MODEL_ID` | `string` | Integration (`openfga`) | Required. OpenFGA Authorization Model ID. |
| `OPENFGA_API_KEY` | `string` | Integration (`openfga`) | Required. API Key for OpenFGA. |

### Cache (Valkey / Redis) Configuration

> **Out of scope.** Valkey/Redis integration is deferred to a future change. No `VALKEY_*` environment variables are injected by this charm.

### Postgres Configuration

| Environment Variable | Type | Source | Details                                                 |
| :--- | :--- | :--- |:--------------------------------------------------------|
| `POSTGRES_HOST` | `string` | Integration (`pg-database`) | Required. Default: `localhost`. PostgreSQL server host. |
| `POSTGRES_PORT` | `int` | Integration (`pg-database`) | Required. Default: `5432`.                              |
| `POSTGRES_USER` | `string` | Integration (`pg-database`) | Required. Default: `authz`. Database user.              |
| `POSTGRES_PASSWORD` | `string` | Integration (`pg-database`) | Default: `authz-password`. Database password.           |
| `POSTGRES_DB` | `string` | Integration (`pg-database`) | Required. Default: `cerberus`. Database name.              |

### Secure Token Service (STS) Configuration

| Environment Variable | Type | Source | Details |
| :--- | :--- | :--- | :--- |
| `EXTAUTHZ_JWK_SET_URL` | `string` | Integration (`sts-info`) | Required. Sourced from `StsInfoData.jwks_set_url`. |
| `STS_ADDRESS` | `string` | Integration (`sts-info`) | Required. gRPC address of the upstream STS service. Sourced from `StsInfoData.grpc_address`. |
| `STS_USE_TLS` | `bool` | Integration (`sts-info`) | Default: `false`. Toggles TLS transport connection security. Sourced from `StsInfoData.tls_enabled`. |

### Logging Configuration

| Environment Variable | Type | Source | Details |
| :--- | :--- | :--- | :--- |
| `LOG_LEVEL` | `string` | Charm Config | Required. Default: `info`. Must be one of: `debug`, `info`, `warn`, or `error`. |
| `LOG_FORMAT` | `string` | Charm (static) | Fixed value: `json`. |

### Telemetry Configuration

| Environment Variable | Type | Source | Details                                                                                  |
| :--- | :--- | :--- |:-----------------------------------------------------------------------------------------|
| `TELEMETRY_ENABLED` | `bool` | Integration (`tracing`) | Default: `false`. Automatically switches to `true` if the tracing integration is joined. |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| `string`| Integration (`tracing`) | OpenTelemetry Collector HTTP scraper endpoint (OTLP).                                    |
| `OTEL_SERVICE_NAME` | `string` | Charm (static) | Set to `authorization-service` if `TELEMETRY_ENABLED=true`.                              |

---

## Integrations Matrix

| Relation            | Interface | Provider                | Direction                                              | Payload Summary                                                                           |
|:--------------------| :--- |:------------------------|:-------------------------------------------------------|:------------------------------------------------------------------------------------------|
| `pg-database`       | `data_platform_libs.v0.data_interfaces` (`postgresql_client`) | `postgresql-k8s`        | `postgresql-k8s` &rarr; `authorization-service`        | DB endpoints, connection credentials, allocated database schema name.                     |
| `openfga`           | `openfga_k8s.v1.openfga` | `openfga-k8s`           | `openfga-k8s` &rarr; `authorization-service`           | Store ID, model ID, structural API token keys, base network address.                      |
| `sts-info`          | `charms.secure_token_service.v0.sts_info` (`sts_info`) | `secure-token-service`  | `secure-token-service` &rarr; `authorization-service`  | HTTP address, gRPC address, JWKS set URL, TLS flag. Used for `EXTAUTHZ_JWK_SET_URL`, `STS_ADDRESS`, `STS_USE_TLS`. |
| `ingress`           | `charmlibs.interfaces.istio_ingress_route` | `istio-ingress-k8s`     | `ingress` &rarr; `authorization-service`               | Public routing constructs, paths, and platform gateway rules for REST API (port 8070). Encapsulated in `IstioIngressIntegration`; `submit_routes()` registers `/v1` prefix route; listener port is 443 (TLS) or 80 (plain). |
| `forward-auth`      | `charms.oauth2_proxy_k8s.v0.forward_auth` (`forward_auth`) | `istio-ingress-k8s`     | `authorization-service` &rarr; `istio-ingress-k8s`     | Authorization service provides `decisions_address` (`grpc://<app>.<model>.svc.cluster.local:9091`) and `app_names` so Istio delegates `envoy.service.auth.v3.Authorization/Check` calls to the service. |
| `kafka` _(future)_  | `kafka_k8s.v0.kafka` | `kafka-k8s`             | `kafka-k8s` &rarr; `authorization-service`             | Out of scope for this change. Tracked separately.                                         |
| `logging`           | `loki_k8s.v1.loki_push_api` | `loki-k8s`              | `loki-k8s` &rarr; `authorization-service`              | Managed `log_level` and format strings; passes Loki alert thresholds.                     |
| `tracing`           | `tempo_coordinator_k8s.v0.tracing` | `tempo-coordinator-k8s` | `tempo-coordinator-k8s` &rarr; `authorization-service` | Telemetry provider descriptors and OTLP endpoints.                                        |
| `grafana-dashboard` | `grafana_k8s.v0.grafana_dashboard` | `grafana-k8s`           | `authorization-service` &rarr; `grafana-k8s`           | Grafana dashboard template for Authorization Service.                                     |


### Design Pattern: Physical Separation & Data Flow

- **`src/charm.py`**: Orchestrator — events, holistic handler. Keep minimal.
- **`src/services.py`**: `WorkloadService` + `PebbleService`.
- **`src/configs.py`**: `CharmConfig` — validates charm config.
- **`src/integrations.py`**: Relation wrappers, data transformation, `EnvVarConvertible` implementations.
- **`src/secret.py`**: Juju secrets management.
- **`src/cli.py`**: Wraps `/usr/bin/app` CLI via Pebble exec.
- **`src/constants.py`**: String constants, integration names, ports.
- **`src/env_vars.py`**: `DEFAULT_CONTAINER_ENV`, `EnvVarConvertible` protocol.
- **`src/exceptions.py`**: Custom exception hierarchy.
- **`src/utils.py`**: Condition factories and decorators (`container_connectivity`, `leader_unit`).

Data flows: **Sources** (Config, Relations, Secrets) → `charm.py` → **Sinks** (Pebble Layer, Relation Databags).
All data sources implement `EnvVarConvertible` (`to_env_vars() -> EnvVars`).
Integration data classes are `@dataclass(frozen=True)` with `load(requirer)` classmethods (mirroring `tenant-service-operator`). Pydantic validation is used inside `.load()` or in `CharmConfig` where input is genuinely untrusted (charm config, relation databags that may be malformed); plain dataclasses are the outer representation.
`charm.py` exposes `_pebble_layer` as a `@property` calling `PebbleService.render_pebble_layer(*sources)`, and applies it via `PebbleService.plan(layer)`. Long-lived computations (database config, integration data) are cached with `@cached_property`. Side-effect operations (migration, secret creation, relation data publishing) are encapsulated in `_ensure_*()` methods that return `bool` and short-circuit on `False`.

### Design Pattern: Juju Status Mapping

| Status | Semantic | Example triggers |
|---|---|---|
| `BlockedStatus` | Human intervention required | Missing/invalid config, relation removed, resource patch failure |
| `WaitingStatus` | Automatic recovery expected | Pod starting, database credentials not yet available, **pending database migration** |
| `ActiveStatus` | Healthy & serving | Ready to accept traffic after successful reconciliation |
| `MaintenanceStatus` | Internal operation in progress | Upgrade in progress |

### Design Pattern: Coding Conventions

- **File Headers**: Every source file must begin with `# Copyright 2026 Canonical Ltd.\n# See LICENSE file for licensing details.`. Executable entrypoints (e.g., `src/charm.py`) additionally require `#!/usr/bin/env python3` as the first line.
- **Holistic Handler**: Two-level pattern in `charm.py`. `_on_holistic_handler(event: ops.HookEvent)` is the shared event handler entry point; it calls a chain of `_ensure_*()` methods (each returns `bool`, short-circuits on `False`) then applies the Pebble layer via `PebbleService.plan(self._pebble_layer)`. No status is set in any handler.
- **Status**: Reported exclusively via `_on_collect_status(event: ops.CollectStatusEvent)` (`collect-unit-status` hook) using `event.add_status()`. Handlers do not call `self.unit.status = ...` directly.
- **Juju Secrets**: Sensitive data (database passwords, OpenFGA API tokens, etc.) MUST be exchanged via Juju 3.x native secrets. Cleartext credentials MUST NOT reside directly in unencrypted relation databags. Managed via `src/secret.py`.
- **Limit `event.defer()`**: Prefer holistic idempotent reconciliation. Deferral is a last resort.
- **Type Hinting**: Strict. Use `list`, `dict`, `tuple` (not `typing.List`, `typing.Dict`).
- **Logging**: Lazy formatting — `logger.info("key: %s", value)`. No f-strings in log calls.
- **Docstrings**: Google-style for all classes and public methods.
- **Error Handling**: Custom exceptions in `exceptions.py`. Raise from abstraction layers; catch in `charm.py` to influence status via `_on_collect_status`.
- **Control Flow**: EAFP over LBYL.

## Goals / Non-Goals

**Goals:**
- Implement a fully functional, production-ready K8s Charmed Operator for the Authorization Service.
- Manage the Pebble service lifecycle (start, reconfigure, healthcheck).
- Validate and propagate charm configuration (`log_level`, `http_proxy`, `https_proxy`, `no_proxy`, `cpu`, `memory`) to the workload; apply `cpu`/`memory` via `KubernetesComputeResourcesPatch`.
- Integrate with OpenFGA (`openfga_k8s.v1.openfga`) as the required policy engine backend.
- Integrate with PostgreSQL (`pg-database`) for persistent storage, exposing `POSTGRES_*` env vars.
- Integrate with STS (`sts-info`) to source `EXTAUTHZ_JWK_SET_URL`, `STS_ADDRESS`, and `STS_USE_TLS`.
- Expose the service REST API (port 8070) externally via `charmlibs.interfaces.istio_ingress_route`.
- Provide `forward-auth` relation so Istio can delegate authorization decisions to the service gRPC endpoint.
- Publish logs, dashboards, and tracing to the Canonical Observability Stack (COS).
- Achieve ≥ 80% unit-test coverage via `ops.testing` (Context+State) and `pytest`+`mock`.
- Provide integration tests using `jubilant` for smoke-testing real deployments.

**Non-Goals:**
- Implementing the Authorization Service application itself (Cerberus binary).
- Managing TLS termination at the charm level (delegated to ingress).
- Supporting non-Kubernetes (machine) deployments.
- Implementing custom relation libraries (reuse existing vendored libs from `lib/` and `charmlibs-interfaces-istio-ingress-route` from PyPI).
- Valkey/Redis cache integration (deferred to a future change).
- Kafka event streaming integration (deferred to a future change).

## Decisions

### D1: 3-Layer Architecture (Orchestration → Abstraction → Infrastructure)

**Decision**: Strictly enforce the Canonical Identity Team pattern across the full module set defined in the Design Pattern section above: `charm.py` owns only events and status; `services.py` (`WorkloadService` + `PebbleService`) owns workload operations and Pebble health checks; `integrations.py` owns relation wrappers and `EnvVarConvertible` implementations; `configs.py` owns config validation; `clients.py` is reserved for future application-specific HTTP API calls; `secret.py` owns Juju secrets; `cli.py` wraps the workload CLI; `constants.py` centralises all string literals; `env_vars.py` defines the `EnvVarConvertible` protocol and `DEFAULT_CONTAINER_ENV`; `exceptions.py` defines the custom exception hierarchy; `utils.py` provides `container_connectivity` and `leader_unit` condition decorators.

**Rationale**: Established team convention. Improves testability (Layer 2 can be unit-tested without ops machinery) and readability. Prevents the common "god charm" anti-pattern.

**Alternatives considered**: Single-file charm — rejected due to poor testability and maintainability at scale.

### D2: Pydantic for Configuration and Integration Data

**Decision**: Use Pydantic for `CharmConfig` (validates untrusted charm config values such as `log_level`) and inside `integrations.py` `.load()` classmethods to validate malformed relation databag data before constructing the frozen dataclass. Integration data types themselves are `@dataclass(frozen=True)` with `load(requirer)` classmethods — matching the `tenant-service-operator` pattern.

**Rationale**: Pydantic where input is genuinely untrusted (operator config, remote databags) gives early failure with descriptive errors. Frozen dataclasses for the integration data types are lightweight, immutable, and directly usable as `EnvVarConvertible` sources without Pydantic overhead on every property access.

**Alternatives considered**: Pydantic everywhere — rejected; adds overhead for data that is already validated at the boundary. Plain dataclasses everywhere — rejected; loses validation on untrusted config inputs.

### D3: PostgreSQL via `data-platform-libs` `DatabaseRequires`

**Decision**: Use the `DatabaseRequires` class from `lib/charms/data_platform_libs/` to consume the `data_platform_libs.v0.data_interfaces` interface on the `pg-database` relation. Credentials are extracted as discrete `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` env vars (not a DSN).

**Rationale**: Standard, battle-tested library across Canonical operators. Provides a stable event-driven API (`database_created`, `endpoints_changed`) and handles secret management for credentials automatically.

**Alternatives considered**: Direct PostgreSQL client relation parsing — rejected; reimplements existing library with higher maintenance cost.

### D4: Health Checks via Pebble Layer in `services.py`

**Decision**: Define a single Pebble `http` check named `"ready"` (`level: ready`) in `PEBBLE_LAYER_DICT` in `src/services.py`, probing `http://localhost:{HTTP_PORT}/healthz`. No `alive` check — the Authorization Service exposes only `/healthz`. No custom HTTP client (`clients.py`) is used for health probing.

**Rationale**: Pebble manages the check lifecycle, retries, and `on-check-failure: restart` behaviour natively. There is no value in duplicating health-probe logic in Python when Pebble already provides it. A single `ready` check is sufficient since the workload only exposes one health endpoint.

**Alternatives considered**: Custom `urllib.request` probe in `clients.py` — rejected; duplicates what Pebble already does. Adding an `alive` check — rejected; the Authorization Service only exposes `/healthz`, so a second check would probe the same endpoint redundantly.

### D5: Pebble Check is Pebble-Managed, Not Charm-Status-Gated

**Decision**: Define a Pebble `http` check with `on-check-failure: restart` in the layer. The charm sets `ActiveStatus` on successful event handling — it does NOT poll the check to determine unit status.

**Rationale**: Mixing health-check polling into the event-driven lifecycle couples two concerns that should be independent. Pebble already handles restart-on-failure autonomously; the charm's job is to react to Juju events. This avoids spurious `WaitingStatus` flicker and deferred events caused by timing races between the charm and the check.

**Alternatives considered**: Gate `ActiveStatus` on `container.get_check("ready").status == "up"` — rejected; creates a tight coupling between charm status and Pebble check timing, requiring event deferral and complicating test setup.

### D6: `ops.testing` Context+State for Unit Tests

**Decision**: All charm-level unit tests use `ops.testing.Context` + `State` objects. No `unittest.mock` of `ops` internals when possible.

**Rationale**: Team's mandated anti-pattern. Context+State tests are declarative, readable, and robust against ops internals changes.

### D8: Follow `tenant-service-operator` Module Structure

**Decision**: Mirror the `tenant-service-operator` module structure and internal patterns throughout: `PebbleService.render_pebble_layer(*sources)` returns a `Layer`; `PebbleService.plan(layer, force_restart)` applies it. `WorkloadService` owns `is_running()`, `is_failing()`, `version` (delegates to `CommandLine.get_service_version()`), and `update_workload_version()` (calls `unit.set_workload_version()`, absorbs exceptions). `cli.py` uses a `CmdExecConfig` dataclass and `_run_cmd()` helper. `utils.py` exposes `container_connectivity` as a plain condition function and `integration_existence(name)` as a factory. `charm.py` uses `_ensure_*()` methods that return `bool` and short-circuit, `@cached_property` for expensive lookups, and a `_pebble_layer` property.

**Rationale**: Consistency with the existing team codebase reduces review friction and onboarding cost. The patterns are proven in production.

### D7: `jubilant` for Integration Tests

**Decision**: Integration tests use the `jubilant` framework.

**Rationale**: Already declared as a project dependency and team standard for integration testing on real K8s clusters.

### D9: Pebble Service Entrypoint

**Decision**: The Pebble layer defines the service command as `/usr/bin/app serve`. This is the entrypoint shipped inside the OCI image for the Authorization Service workload.

**Rationale**: The binary lives at `/usr/bin/app` inside the container. All CLI interactions (version, migrate, migrate status) also use `/usr/bin/app`.

### D10: Database Migration as a Juju Action (Leader-Only)

**Decision**: Database migration is NOT run automatically. On `upgrade_charm`, the charm runs `/usr/bin/app migrate status` to check whether a migration is pending. If migration is needed, the charm reports `WaitingStatus("Waiting for database migration")` via `_on_collect_status` — it does NOT start the workload. The operator then triggers the migration manually by running `juju run <unit> run-migration`. The `run-migration` action handler is leader-only; it calls `CommandLine.run_migration(dsn)` where `dsn` is constructed via `POSTGRESQL_DSN_TEMPLATE` from `DatabaseConfig`, then stores the completed migration version in peer data and calls `_on_holistic_handler()`. If migration is not needed on upgrade, `_on_holistic_handler()` is called directly.

**Rationale**: Running migrations automatically on upgrade risks data loss or corruption in failure scenarios. Operator-controlled migration gives full control over timing (e.g., after a database backup). The `WaitingStatus` signal makes it clear to the operator that action is required without blocking the Juju model.

**Alternatives considered**: Automatic migration on `upgrade_charm` — rejected; no operator control, risk of unrecoverable failure mid-upgrade. Migration as part of `_on_holistic_handler` — rejected; conflates workload reconciliation with schema management.

## Risks / Trade-offs

- **[Risk] `charmcraft.yaml` must be updated to add relation endpoints** → Requires explicit user validation per project governance rules. Document clearly in tasks and gate implementation behind approval.
- **[Risk] OCI image v0.2.0 may evolve** → Pin the image version in `charmcraft.yaml`; update via the normal Renovate bot flow.
- **[Risk] `charmlibs-interfaces-istio-ingress-route` is a PyPI package, not a vendored `charmcraft fetch-lib` library** → Must be listed in `requirements.txt` and included in charm packing; different lifecycle than Charmhub libs.
- **[Risk] Missing `lib/` vendored libraries at implementation time** → Tasks must include a step to `fetch-lib` required charm libraries before implementation. If unavailable, stub them with a `NotImplemented` placeholder and track as a follow-up.

## Open Questions

- ~~Should the charm expose a `grpc` endpoint relation (port 9091) for downstream services to consume policy decisions directly?~~ **Resolved**: gRPC port 9091 has no Juju relation endpoint, but the port IS opened on the unit via `WorkloadService.open_port()` so that Kubernetes network policies allow direct gRPC traffic.
- ~~What Grafana dashboard JSON (if any) does the Authorization Service ship, or must one be authored from scratch?~~ **Resolved**: Scaffold the `GrafanaDashboardProvider` but leave the dashboard empty for now.
- ~~Does `src/cli.py` need to support any specific CLI sub-commands at initial implementation, or is it scaffolded empty and populated incrementally?~~ **Resolved**: `cli.py` wraps `/usr/bin/app` and implements `get_service_version()` (`/usr/bin/app version`), `run_migration(dsn: str)` (`/usr/bin/app migrate --dsn <dsn>`), and `migrate_status() -> bool` (`/usr/bin/app migrate status`). `WorkloadService.version` delegates to `get_service_version()`; `update_workload_version()` calls `unit.set_workload_version()` and absorbs exceptions.
- ~~STS integration deferred — is the `sts-info` interface available?~~ **Resolved**: `charms.secure_token_service.v0.sts_info` is implemented and vendored in `lib/`. Use `StsInfoRequirer` (requirer side only — do not modify the library).
