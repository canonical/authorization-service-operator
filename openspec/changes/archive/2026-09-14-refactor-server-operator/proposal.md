## Why

The existing `authorization-service-operator` contains redundant local implementations of command-line runners, Juju decorators, Pebble service managers, custom exceptions, and configurations parsers. Refactoring the repository to consume the central shared library `authorization-service-operator-shared` streamlines the codebase, simplifies testing, and consolidates common logic. This refactoring focuses the operator exclusively on its core server duties (executing the `serve` subcommand on HTTP/gRPC ports) and cleanly strips away unused Kafka ingestion elements.

## What Changes

- **Add Shared Dependency**: Configure `pyproject.toml` to build with `uv` using PEP 508 direct Git dependency mapping and `[tool.uv.sources]` overrides, and configure `charmcraft.yaml` with `build-packages: [git]`.
- **Codebase Simplification**: Delete redundant local files in `/src` (including `cli.py`, `configs.py`, `services.py`, `exceptions.py`, `utils.py`, `env_vars.py`) and replace them with standard package imports.
- **Refactor Server Reconciliation**: Refactor `src/charm.py` to initialize and leverage shared relation handlers and Pebble/workload managers from `authorization_service_operator_shared`.
- **Exclusive Migration Ownership**: Keep database migration handling and the `run-migration` action exclusively on the Server charm. Workers do not run migrations or expose migration actions.
- **Authorization Service Info Relation**: Provide `AuthorizationServiceInfoProvider` from `authorization_service_operator_shared.info` (`authorization-service-info` endpoint) on the Server charm to publish workload version, migration version status (`MIGRATION_COMPLETED`), `openfga_store_id`, and `openfga_model_id`. Other components (e.g. Workers) require this relation and evaluate status sequentially (`WaitingStatus` for migration mismatch, then `WaitingStatus` for missing OpenFGA model).
- **Remove Kafka Ingestion**: Remove Kafka relations, metadata interfaces, and configuration hooks from the Server's configuration blocks.
- **Pebble Execution**: Map the container startup command exclusively to `/usr/bin/app serve` on HTTP port `8070` and gRPC port `9091`.

## Capabilities

### New Capabilities
- `shared-library-dependency`: Integrates build-time dependency resolution linking the operator to the standard shared library.
- `authorization-service-info-relation`: Uses `authorization_service_operator_shared.info` for sharing workload and database migration state with dependent components via the `authorization-service-info` relation.

### Modified Capabilities
- `server-reconciliation-loop`: Upgrades the main holistic reconciliation loop in `src/charm.py` to initialize shared managers and publish version info upon migration completion.
- `kafka-ingestion-removal`: Removes Kafka relations, configuration hooks, and unused event handlers from the operator layout.

## Impact

- **Code Size**: Drastically reduces local lines of code.
- **Maintainability**: Centralizes relation and service planning modifications within the shared repository.
- **Memory footprint**: Removes unused listener threads from the Server execution layer.
