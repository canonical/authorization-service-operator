## 1. Project Scaffolding

- [x] 1.1 Create `src/` directory with stub files for all modules (`charm.py`, `services.py`, `configs.py`, `integrations.py`, `clients.py`, `secret.py`, `cli.py`, `constants.py`, `env_vars.py`, `exceptions.py`, `utils.py`) and `__init__.py`; add copyright header (`# Copyright 2026 Canonical Ltd.\n# See LICENSE file for licensing details.`) to every file; add `#!/usr/bin/env python3` shebang to `src/charm.py`
- [x] 1.2 Create `tests/unit/` and `tests/integration/` directories with empty `__init__.py` files
- [x] 1.3 Add `requirements.txt` with runtime dependencies: `ops`, `pydantic`
- [x] 1.4 Confirm or fetch required charm libraries: via `charmcraft fetch-lib`: `data_platform_libs` (DatabaseRequires), `openfga_k8s` (OpenFGARequires), `tempo_coordinator_k8s` (TracingEndpointRequirer), `loki_k8s` (LogProxyConsumer), `grafana_k8s` (GrafanaDashboardProvider), `observability_libs` (KubernetesComputeResourcesPatch), `oauth2_proxy_k8s` (ForwardAuthProvider). `sts_info` is already vendored in `lib/`. Add `charmlibs-interfaces-istio-ingress-route` to `requirements.txt` (PyPI package — **not** a charmcraft lib).

## 2. Foundation Modules

- [x] 2.1 Implement `src/constants.py`: define string constants for container/service name (`"authorization-service"`), Pebble check name, relation names (`pg-database`, `openfga`, `tracing`, `ingress`, `grafana-dashboard`, `logging`, `sts-info`, `forward-auth`), `GRPC_PORT=9091`, `HTTP_PORT=8070`
- [x] 2.2 Implement `src/exceptions.py`: define custom exception hierarchy — base `AuthorizationServiceCharmError`, `ConfigError`, `IntegrationDataError`, `WorkloadError`
- [x] 2.3 Implement `src/env_vars.py`: define `EnvVars: TypeAlias = Mapping[str, str | bool]`, the `EnvVarConvertible` Protocol (`to_env_vars() -> EnvVars`), and `DEFAULT_CONTAINER_ENV` dict containing all static env vars: `GRPC_PORT=9091`, `HTTP_PORT=8070`, `LOG_FORMAT=json`, `TELEMETRY_ENABLED=false`, `OTEL_SERVICE_NAME=authorization-service`
- [x] 2.4 Write unit tests in `tests/unit/test_env_vars.py` covering: `DEFAULT_CONTAINER_ENV` contains all expected static keys and values (no `VALKEY_*`, no `EXTAUTHZ_JWK_SET_URL`); protocol structural check

## 3. Configuration Layer (`src/configs.py`)

- [x] 3.1 Implement `CharmConfig` as a plain class `__init__(self, config: ConfigData)` that stores and validates config values internally (using Pydantic or manual validation); fields: `log_level` (validated against `debug|info|warn|error`), `dev: bool`, `http_proxy: str | None`, `https_proxy: str | None`, `no_proxy: str | None`, `cpu: str | None`, `memory: str | None`
- [x] 3.2 Add `from_charm(charm) -> "CharmConfig"` classmethod that reads `charm.config` and returns a validated `CharmConfig` or raises `ConfigError`
- [x] 3.3 Implement `to_env_vars() -> EnvVars` mapping config fields to env var names: `log_level` → `LOG_LEVEL`, `dev` → `DEV`, `http_proxy` → `HTTP_PROXY`, `https_proxy` → `HTTPS_PROXY`, `no_proxy` → `NO_PROXY`; omits unset optional proxy fields. `cpu` and `memory` are NOT mapped to env vars — they are handled by `KubernetesComputeResourcesPatch`.
- [x] 3.4 Write unit tests in `tests/unit/test_configs.py` covering: valid `log_level` values, invalid value raises `ConfigError`, `to_env_vars()` output for all env-var fields; `cpu`/`memory` not present in `to_env_vars()` output

## 4. Secrets Layer (`src/secret.py`)

- [x] 4.1 Implement helpers in `src/secret.py` to retrieve and cache Juju 3.x secrets by label or URI via `ops.model.SecretNotFoundError`-safe accessors; these helpers MUST be used by integration wrappers whenever credential fields (passwords, API tokens) are retrieved from relation databags — cleartext credentials must never be read directly from unencrypted databag entries
- [x] 4.2 Write unit tests in `tests/unit/test_secret.py` using `ops.testing` State with `Secret` objects covering: secret found, secret missing, secret rotation

## 5. Service Layer (`src/services.py`)

- [x] 5.1 Define `PEBBLE_LAYER_DICT: LayerDict` module-level constant with the base layer template: service `"authorization-service"`, command `/usr/bin/app serve`, `startup: enabled`, `on-check-failure: {"ready": "restart"}`; one Pebble `http` check: `"ready"` (`level: ready`, url `http://localhost:{HTTP_PORT}/healthz`)
- [x] 5.2 Implement `PebbleService` class wrapping a `Container` reference, providing:
  - `render_pebble_layer(*env_var_sources: EnvVarConvertible) -> Layer` — deep-merges `DEFAULT_CONTAINER_ENV` with `to_env_vars()` from each source in order, returns a `Layer` built from `PEBBLE_LAYER_DICT` with merged env vars
  - `plan(layer: Layer, force_restart: bool = False)` — adds the layer, restarts the service if the plan changed or `force_restart=True`
  - `stop()` — stops the service
- [x] 5.3 Implement `WorkloadService` class wrapping a `Unit` and a `CommandLine`, providing:
  - `version: str` property — delegates to `self._cli.get_service_version()`
  - `update_workload_version()` — calls `self.version`; if non-empty calls `self._unit.set_workload_version(version)`; logs error and returns on exception (does not raise)
  - `is_running() -> bool` — checks Pebble service + check status
  - `is_failing() -> bool` — checks Pebble check failure state
  - `open_port()` — opens both `HTTP_PORT` and `GRPC_PORT` on the unit
- [x] 5.4 Write unit tests in `tests/unit/test_services.py` using `pytest`+`unittest.mock` covering: `render_pebble_layer` merges env vars correctly; `plan` restarts on change and skips restart when unchanged; `plan` force-restarts when `force_restart=True`; `stop`; `is_running` true/false; `is_failing`; `update_workload_version` sets version when `get_service_version` returns a non-empty string; `update_workload_version` is a no-op when version is empty; `update_workload_version` logs error and does not raise when `set_workload_version` throws; `open_port` opens both HTTP_PORT and GRPC_PORT

## 6. CLI Wrapper (`src/cli.py`)

- [x] 6.1 Define `CmdExecConfig` dataclass: `service_context: str`, `environment: dict[str, str]`, `timeout: int`, `stdin: str | None`
- [x] 6.2 Implement `CommandLine` class wrapping the Pebble `Container`; add `_run_cmd(cmd: list[str], exec_config: CmdExecConfig) -> tuple[str, str]` internal helper that calls `container.exec()` and returns `(stdout, stderr)`, raising `WorkloadError` on non-zero exit
- [x] 6.3 Implement `get_service_version() -> str` — runs `/usr/bin/app version` via `_run_cmd`, returns version string; raises `WorkloadError` on failure
- [x] 6.4 Implement `run_migration(dsn: str)` — runs `/usr/bin/app migrate --dsn <dsn>` via `_run_cmd`; raises `WorkloadError` on non-zero exit
- [x] 6.5 Implement `migrate_status() -> bool` — runs `/usr/bin/app migrate status` via `_run_cmd`; returns `True` if migration is pending (non-zero exit code or stdout indicates pending), `False` if up-to-date; raises `WorkloadError` on unexpected failure
- [x] 6.6 Write unit tests in `tests/unit/test_cli.py` using `ops.testing` Container `Exec` mocks covering: `get_service_version()` success; non-zero exit raises `WorkloadError`; `run_migration(dsn)` success; non-zero exit raises `WorkloadError`; `migrate_status()` returns `True` when migration pending; `migrate_status()` returns `False` when up-to-date

## 7. Utils (`src/utils.py`)

- [x] 7.1 Implement `container_connectivity(charm) -> bool` — plain condition function (NOT a decorator factory) that returns `False` and sets `WaitingStatus` if `container.can_connect()` is `False`; used in handlers as `if not container_connectivity(self): return`
- [x] 7.2 Implement `leader_unit` decorator — returns early for non-leader units where leader-only logic is required
- [x] 7.3 Implement `integration_existence(name: str) -> Condition` factory returning a condition function that returns `False` and sets `BlockedStatus` if the named relation has no active integration; instantiate module-level helpers `database_integration_exists`, `openfga_integration_exists`
- [x] 7.4 Write unit tests in `tests/unit/test_utils.py` covering: `container_connectivity` returns `True` when connected, `False` when not; `leader_unit` skips handler on non-leader; `integration_existence` condition True/False cases

## 8. Integration Wrappers (`src/integrations.py`)

- [x] 8.1 Define `DatabaseConfig` as `@dataclass(frozen=True, slots=True)` with fields `host`, `port`, `dbname`, `username`, `password`; implement `to_env_vars() -> EnvVars` returning `{"POSTGRES_HOST": ..., "POSTGRES_PORT": ..., "POSTGRES_USER": ..., "POSTGRES_PASSWORD": ..., "POSTGRES_DB": ...}`; add `load(requirer: DatabaseRequires) -> "DatabaseConfig | None"` classmethod that reads relation databag data, uses Pydantic internally to validate before constructing the dataclass, and raises `IntegrationDataError` on malformed data
- [x] 8.2 Define `OpenFGAConfig` as `@dataclass(frozen=True, slots=True)` with fields `address`, `store_id`, `authz_model_id`, `api_key`; implement `to_env_vars() -> EnvVars` returning `{"OPENFGA_ADDRESS": ..., "OPENFGA_STORE_ID": ..., "OPENFGA_AUTHZ_MODEL_ID": ..., "OPENFGA_API_KEY": ...}`; add `load(requirer: OpenFGARequires) -> "OpenFGAConfig | None"` classmethod with Pydantic validation inside, raising `IntegrationDataError` on malformed data
- [x] 8.3 Define `TracingConfig` as `@dataclass(frozen=True, slots=True)` with field `otlp_endpoint`; implement `to_env_vars() -> EnvVars` returning `{"TELEMETRY_ENABLED": True, "OTEL_EXPORTER_OTLP_ENDPOINT": ...}`; add `load(requirer: TracingEndpointRequirer) -> "TracingConfig | None"` classmethod
- [x] 8.4 Define `StsConfig` as `@dataclass(frozen=True, slots=True)` with fields `jwks_set_url: str`, `grpc_address: str`, `tls_enabled: bool`; implement `to_env_vars() -> EnvVars` returning `{"EXTAUTHZ_JWK_SET_URL": jwks_set_url, "STS_ADDRESS": grpc_address, "STS_USE_TLS": str(tls_enabled).lower()}`; add `load(requirer: StsInfoRequirer) -> "StsConfig | None"` classmethod using `requirer.get_sts_info()` — catch `StsInfoRelationError` and return `None`; raise `IntegrationDataError` only on unexpected exceptions
- [x] 8.5 Define `IstioIngressIntegration` class in `src/integrations.py` wrapping `IstioIngressRouteRequirer`; expose `external_url: str | None` property (constructs `https://host` or `http://host` based on `requirer.tls_enabled`); expose `submit_routes()` method that builds and submits `IstioIngressRouteConfig` with a single `Listener` at `INGRESS_HTTPS_PORT` (443) when TLS enabled or `INGRESS_HTTP_PORT` (80) otherwise, and a single `HTTPRoute` matching path prefix `/v1` with `BackendRef(service=app_name, port=HTTP_PORT)`
- [x] 8.6 Write unit tests in `tests/unit/test_integrations.py` covering: `IstioIngressIntegration.external_url` returns `https://host` when TLS enabled and `http://host` otherwise; `submit_routes()` calls `requirer.submit_config()` with listener port `INGRESS_HTTPS_PORT` when TLS enabled or `INGRESS_HTTP_PORT` otherwise; route prefix is `/v1`; `StsConfig.load()` returns `StsConfig()` default on `StsInfoRelationMissingError`; `TracingConfig.load()` returns `TracingConfig()` default when no relation

## 9. Orchestration Layer (`src/charm.py`)

- [x] 9.1 Create `AuthorizationServiceCharm(ops.CharmBase)` skeleton with `__init__` instantiating `PebbleService`, `WorkloadService`, `CommandLine`, `KubernetesComputeResourcesPatch`, `StsInfoRequirer`, `IstioIngressRouteRequirer`, `AuthProxyRequirer`, and all integration/COS library providers; bind all event handlers; use lazy log formatting and Google-style docstrings throughout
- [x] 9.2 Add `@cached_property` accessors for expensive/repeated lookups: `_charm_config: CharmConfig | None`, `_database_config: DatabaseConfig | None`, `_openfga_config: OpenFGAConfig | None`, `_tracing_config: TracingConfig | None`, `_sts_config: StsConfig | None`
- [x] 9.3 Add `_pebble_layer` as a `@property` that calls `_pebble_service.render_pebble_layer(charm_config, database_config, openfga_config, sts_config, tracing_config, ...)` with all available `EnvVarConvertible` sources (skipping `None` values)
- [x] 9.4 Implement `_ensure_container() -> bool` — returns `False` (setting `WaitingStatus`) if container is not connectable; used by all handlers
- [x] 9.5 Implement `_ensure_database() -> bool` — returns `False` (setting `BlockedStatus`) if `_database_config` is `None`
- [x] 9.6 Implement `_ensure_openfga() -> bool` — returns `False` (setting `BlockedStatus`) if `_openfga_config` is `None`
- [x] 9.7 Implement `_on_holistic_handler(event: ops.HookEvent)`: calls `_ensure_container()`, `_ensure_database()`, `_ensure_openfga()` in order; short-circuits on first `False`; on all `True`, calls `_pebble_service.plan(self._pebble_layer)`
- [x] 9.8 Implement `_on_pebble_ready(event)`: calls `_on_holistic_handler(event)`; on success calls `_workload_service.update_workload_version()` (already handles its own errors internally)
- [x] 9.9 Register `_on_holistic_handler` as the handler for: `config_changed`, `database_created`, `database_endpoints_changed`, `openfga_store_created`, `tracing_relation_changed`, `sts_info_relation_updated` (from `StsInfoRequirer.on.sts_info_relation_updated`)
- [x] 9.10 Implement `_on_database_relation_broken(event)`: stop service; call `_on_holistic_handler(event)`
- [x] 9.11 Implement `_on_openfga_store_created(event)` and `_on_openfga_store_removed(event)` using typed `OpenFGAStoreCreateEvent`/`OpenFGAStoreRemovedEvent`; store_removed stops service and calls `_on_holistic_handler(event)`
- [x] 9.12 Implement `_on_tracing_relation_broken(event)`: call `_on_holistic_handler(event)`
- [x] 9.13 Implement `_on_sts_relation_broken(event)`: call `_on_holistic_handler(event)` (STS is optional — no service stop required)
- [x] 9.14 Implement `_on_ingress_ready(event)` (mapped to `IstioIngressIntegration.requirer.on.ready`): call `self.istio_ingress.submit_routes()`; read `self.istio_ingress.external_url`; log with lazy formatting. No `data_removed` handler needed.
- [x] 9.15 Implement `_on_upgrade_charm(event)`: check container connectivity; run `_cli.migrate_status()` — if `True`, return (WaitingStatus is reported via `_on_collect_status`); if `False` (migration not needed), call `_on_holistic_handler(event)`; on `WorkloadError` from `migrate_status()`, log and return with WaitingStatus
- [x] 9.16 Implement `_on_run_migration_action(event: ops.ActionEvent)`: leader-only (return `event.fail("only the leader can run migrations")` for non-leaders); ensure container connectivity; call `_cli.run_migration(dsn)` with DSN from `POSTGRESQL_DSN_TEMPLATE`; on success store current workload version in peer data and call `_on_holistic_handler(event)`; on `WorkloadError` call `event.fail(str(e))`
- ~~9.17 Implement `_on_remove(event)`: not required for authorization service~~
- [x] 9.18 Implement `_on_collect_status(event: ops.CollectStatusEvent)`: registered to `collect_unit_status`; inspect current state and call `event.add_status()` — `BlockedStatus` if config invalid, `pg-database` absent/broken, `openfga` absent/broken, or `resources_patch` failed; `WaitingStatus` if container not connectable, required credential pending, or migration pending; `ActiveStatus` when workload running and all required sources satisfied; delegate to `resources_patch.get_status()` for the resource patch state
- [x] 9.19 Wire up COS library event handlers (LogProxyConsumer, GrafanaDashboardProvider, TracingEndpointRequirer) in `__init__`
- [x] 9.20 Add `_resource_spec_from_config() -> ResourceRequirements` helper used by `KubernetesComputeResourcesPatch`; constructs `ResourceRequirements(limits={...}, requests={...})` from `_charm_config.cpu` and `_charm_config.memory`, omitting keys that are `None` or empty
- [x] 9.21 Declare `StoredState` on the charm class with field `migration_pending: bool = False`

## 9a. Juju Actions

- [x] 9a.1 ⚠️ **USER VALIDATION REQUIRED**: Add `run-migration` action to `charmcraft.yaml` (description: "Run pending database migrations. Must be executed on the leader unit.") and await approval
- [x] 9a.2 Register `_on_run_migration_action` in `charm.py` `__init__` for the `run-migration` action event
- [x] 9a.3 Write unit tests in `tests/unit/test_charm.py` covering:
  - `run-migration` action on leader with valid DB config → `run_migration(dsn)` called, holistic handler runs, `ActiveStatus`
  - `run-migration` action on non-leader → `event.fail()` called with appropriate message
  - `run-migration` action where `run_migration(dsn)` raises `WorkloadError` → `event.fail()` called

## 10. `charmcraft.yaml` Relation Endpoints (Requires User Validation)

- [x] 10.1 ⚠️ **USER VALIDATION REQUIRED**: Propose additions to `charmcraft.yaml` for the following and await approval before committing:
  - Config options (currently only `log_level` exists):
    - `cpu` (type: string, optional — Kubernetes CPU resource value, e.g. `"500m"`)
    - `memory` (type: string, optional — Kubernetes memory resource value, e.g. `"256Mi"`)
  - Relation endpoints:
    - `requires: pg-database` (interface: `data_platform_libs.v0.data_interfaces`, limit: 1)
    - `requires: openfga` (interface: `openfga_k8s.v1.openfga`, limit: 1)
    - `requires: ingress` (interface: `istio_ingress_route`, limit: 1)
    - `requires: sts-info` (interface: `sts_info`, limit: 1)
    - `requires: tracing` (interface: `tempo_coordinator_k8s.v0.tracing`, limit: 1)
    - `provides: forward-auth` (interface: `forward_auth`)
    - `provides: logging` (interface: `loki_k8s.v1.loki_push_api`)
    - `provides: grafana-dashboard` (interface: `grafana_dashboard`)
- [x] 10.2 Apply approved `charmcraft.yaml` changes (relations, config, and `run-migration` action)

## 11. Unit Tests — Charm State (`tests/unit/test_charm.py`)

- [x] 11.1 Create `conftest.py` module-level `create_state()` factory (NOT a fixture) building `testing.State` with sane defaults; define relation fixtures for database, openfga, sts-info, ingress, and forward-auth; add autouse fixtures for resource patches (`KubernetesComputeResourcesPatch`)
- [x] 11.2 Test: `pebble_ready` with `pg-database` + `openfga` satisfied → `collect_unit_status` yields `ActiveStatus`, workload version set
- [x] 11.3 Test: `pebble_ready` with missing `pg-database` → `collect_unit_status` yields `BlockedStatus`
- [x] 11.4 Test: `pebble_ready` with missing `openfga` → `collect_unit_status` yields `BlockedStatus`
- [x] 11.5 Test: `pebble_ready` where `get_service_version()` raises → `collect_unit_status` still yields `ActiveStatus`
- [x] 11.6 Test: `config_changed` with invalid `log_level` → `collect_unit_status` yields `BlockedStatus`
- [x] 11.7 Test: `config_changed` with valid config and all required relations → pebble layer applied with correct env vars
- [x] 11.8 Test: `database_relation_broken` → service stopped, `collect_unit_status` yields `BlockedStatus`
- [x] 11.9 Test: `openfga_relation_broken` → service stopped, `collect_unit_status` yields `BlockedStatus`
- [x] 11.10 Test: `tracing_relation_changed` → `TELEMETRY_ENABLED=true` in Pebble layer env
- [x] 11.11 Test: `upgrade_charm` where `migrate_status()` returns `False` (no migration needed) → holistic handler runs, `collect_unit_status` yields `ActiveStatus`
- [x] 11.12 Test: `upgrade_charm` where `migrate_status()` returns `True` → `migration_pending` stored, `collect_unit_status` yields `WaitingStatus("Waiting for database migration")`, pebble plan NOT applied
- [x] 11.13 Test: `upgrade_charm` where `migrate_status()` raises `WorkloadError` → proceeds to holistic handler (error is logged, falls back to False)
- [x] 11.14 Test: `sts_info_relation_updated` with valid STS data → `EXTAUTHZ_JWK_SET_URL`, `STS_ADDRESS`, `STS_USE_TLS` present in Pebble layer env
- [x] 11.15 Test: `sts_info` relation broken → STS env vars absent from Pebble layer env; unit stays `ActiveStatus` (STS is optional)
- [x] 11.16 Test: `forward-auth` relation created → `ForwardAuthProvider._update_relation_data` called with `decisions_address=grpc://<app>.<model>.svc.cluster.local:9091` and `app_names=[app_name]`
- ~~11.17 Test: ingress `data_removed` event → removed~~ **Removed**: `data_removed` event is not observed; no `_on_ingress_revoked` handler.
- [x] 11.18 Test: `patch_failed` event from `KubernetesComputeResourcesPatch` → `collect_unit_status` yields `BlockedStatus`

## 12. Integration Tests (`tests/integration/test_charm.py`)

- [x] 12.1 Write a `jubilant`-based smoke test: deploy the charm + `pg-database` + `openfga`, assert unit reaches `active/idle`
- [x] 12.2 Write a config test: set an invalid `log_level`, assert unit enters `blocked`; set a valid one, assert unit returns to `active`
- [x] 12.3 Write a relation-removal test: remove the `pg-database` relation, assert unit enters `blocked`
- [x] 12.4 Write a relation-removal test: remove the `openfga` relation, assert unit enters `blocked`
- [x] 12.5 Write an upgrade/migration test: simulate upgrade where migration is pending → assert unit enters `waiting`; run `juju run <unit> run-migration` → assert unit returns to `active`

## 13. Verification

- [x] 13.1 Run `tox -e fmt` and resolve all formatting issues
- [x] 13.2 Run `tox -e lint` and resolve all linting/type errors (mypy, codespell)
- [x] 13.3 Run `tox -e unit` and verify ≥ 80% coverage
- [x] 13.4 Run `charmcraft pack` to confirm the charm builds without errors

## 14. Future Work (Out of Scope)

- [x] 14.1 _(Future)_ Implement `kafka-integration` capability once the Kafka integration is prioritised — consume Kafka connection details and include in workload env vars.
- [x] 14.2 _(Future)_ Implement Valkey/Redis cache integration once an operator-managed integration becomes available.
