## Why

The Canonical centralized identity solution requires a production-ready Policy Decision Point (PDP) to externalize authorization decisions across services. The Authorization Service (Cerberus) is that PDP, and a Charmed Operator is needed to deploy, configure, and integrate it within a Juju-managed Kubernetes environment — enabling lifecycle management, observability, and first-class integration with the rest of the identity platform.

## What Changes

- Introduce `src/charm.py`: top-level orchestration layer handling all Juju events and unit status transitions.
- Introduce `src/services.py`: `WorkloadService` + `PebbleService` — workload orchestration and low-level Pebble operations.
- Introduce `src/configs.py`: `CharmConfig` — validates charm config options and implements `EnvVarConvertible`.
- Introduce `src/integrations.py`: strongly-typed Pydantic relation wrappers implementing `EnvVarConvertible`.
- Introduce `src/clients.py`: HTTP client for probing the Authorization Service health endpoint.
- Introduce `src/secret.py`: Juju secrets management helpers.
- Introduce `src/cli.py`: wraps the `authorization-service` CLI via Pebble exec.
- Introduce `src/constants.py`: string constants, integration names, ports.
- Introduce `src/env_vars.py`: `EnvVarConvertible` protocol and `DEFAULT_CONTAINER_ENV`.
- Introduce `src/exceptions.py`: custom exception hierarchy.
- Introduce `src/utils.py`: `container_connectivity` and `leader_unit` condition decorators.
- Add unit tests in `tests/unit/test_charm.py` (ops.testing / Context+State pattern) and `tests/unit/test_services.py` (pytest + mock).
- Add integration tests in `tests/integration/` using the `jubilant` framework.
- Update `charmcraft.yaml` with relation endpoints for database, ingress, and observability.

## Capabilities

### New Capabilities

- `workload-lifecycle`: Manage the `authorization-service` Pebble service — start, stop, reconfigure, health-check. Includes required OpenFGA integration (`openfga_k8s.v1.openfga`).
- `charm-configuration`: Validate and apply all charm config options (`log_level`, `dev`, proxy vars, `cpu`, `memory`) to the workload via `EnvVarConvertible`; apply `cpu`/`memory` to the Kubernetes container via `KubernetesComputeResourcesPatch`.
- `database-integration`: Integrate with PostgreSQL via the `pg-database` relation (`data_platform_libs.v0.data_interfaces`), supplying `POSTGRES_*` environment variables.
- `ingress-integration`: Expose the Authorization Service REST API (port 8070) via the `istio-ingress-route` interface (`charmlibs.interfaces.istio_ingress_route`), provided by `istio-ingress-k8s`.
- `sts-integration`: Consume STS endpoint info via the `sts-info` relation (`charms.secure_token_service.v0.sts_info`), supplying `EXTAUTHZ_JWK_SET_URL`, `STS_USE_TLS`, and `STS_ADDRESS` environment variables.
- `forward-auth-integration`: Provide authorization decisions to Istio via the `forward-auth` relation (`charms.oauth2_proxy_k8s.v0.forward_auth`), advertising the gRPC endpoint as `decisions_address` so Istio delegates `envoy.service.auth.v3.Authorization/Check` calls to the service.
- `observability-integration`: Provide logs (`loki_k8s.v1.loki_push_api`), dashboards (`grafana_dashboard`), distributed tracing (`tempo_coordinator_k8s.v0.tracing`), and compute resource metrics to the Canonical Observability Stack.

> **Future capability (out of scope):** `kafka-integration` — Optional Kafka event streaming (`kafka_k8s.v0.kafka`). Deferred to a separate change.

### Modified Capabilities

## Impact

- **New files**: `src/charm.py`, `src/services.py`, `src/configs.py`, `src/integrations.py`, `src/clients.py`, `src/secret.py`, `src/cli.py`, `src/constants.py`, `src/env_vars.py`, `src/exceptions.py`, `src/utils.py`
- **New tests**: `tests/unit/test_charm.py`, `tests/unit/test_services.py`, `tests/integration/test_charm.py`
- **`charmcraft.yaml`**: Requires update to add relation endpoints (requires user validation per governance rules).
- **Dependencies**: `ops`, `pydantic`, `lightkube`, `lightkube-models`, `charmlibs-interfaces-istio-ingress-route`, `jsonschema` (via `requirements.txt`).
- No breaking changes to any existing interfaces (greenfield implementation).
