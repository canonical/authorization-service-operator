## Context

The `authorization-service-operator` functions as the main Policy Decision Point (PDP) Server component within the Charmed Authorization Service family. In its current form, it carries redundant copies of relation parsing, command execution, exception models, and container planning utilities that are now consolidated into the shared library `authorization-service-operator-shared`. 

This design outlines how to refactor this operator to delete its redundant local modules, link against the shared library via `pyproject.toml` and Charmcraft `uv` layers (with `build-packages: [git]` in `charmcraft.yaml`), and configure the startup environment exclusively for the `serve` subcommand on HTTP (8070) and gRPC (9091) ports. In addition, the design outlines the complete removal of the unused Kafka relation layer, focusing the charm entirely on serving API evaluations and PDP queries.

## Goals / Non-Goals

**Goals:**
- **Shared Package Integration**: Add compile-time and runtime dependency configuration in `pyproject.toml` pointing to `authorization-service-operator-shared` via PEP 508 direct git URL and `[tool.uv.sources]`, and configure `charmcraft.yaml` with `build-packages: [git]` for isolated packaging support.
- **Redundancy Cleanup**: Delete local `/src` duplicate files: `cli.py`, `configs.py`, `services.py`, `exceptions.py`, `utils.py`, and `env_vars.py`.
- **Reconciliation Refactoring**: Clean up `src/charm.py` to import common decorators, exceptions, configurations, database handlers, and Pebble service planners directly from the shared library namespace.
- **Exclusive Migration Ownership**: Keep database migration handling and the `run-migration` action exclusively on the Server charm.
- **Authorization Service Info Relation**: Distribute `AuthorizationServiceInfoProvider` and `AuthorizationServiceInfoRequirer` in `authorization_service_operator_shared.info` (`authorization-service-info` endpoint) on the Server charm to share `workload_version`, `migration_version`, `openfga_store_id`, and `openfga_model_id`.
- **Kafka Relation Removal**: Remove the Kafka interface, configuration tokens, metadata hooks, and event-handler loops from the Server's configuration blocks.
- **Startup Command Mapping**: Configure the Pebble layer startup target to run `/usr/bin/app serve` on the container's ports.

**Non-Goals:**
- **Worker Migration Action**: Worker and Listener charms will not expose the `run-migration` action or carry out database migrations. They rely on the Server charm to run migrations and read version info over `authorization-service-info`.

## Decisions

### Decision 1: Shared Import Adoption and Local File Cleanup
- **Choice**: Direct, clean deletion of local helper files and switching to shared imports.
- **Rationale**: Keeps the operator small, highly specialized, and ensures any shared improvements (like security or TLS enhancements) cascade down instantly without duplicate patch updates.
- **Import Mapping**:
  ```python
  from authorization_service_operator_shared.database import DatabaseRelationHandler
  from authorization_service_operator_shared.openfga import OpenFGARelationHandler
  from authorization_service_operator_shared.sts import STSRelationHandler
  from authorization_service_operator_shared.services import PebbleService, WorkloadService
  from authorization_service_operator_shared.configs import CharmConfig
  from authorization_service_operator_shared.utils import container_connectivity
  from authorization_service_operator_shared.info import AuthorizationServiceInfoProvider
  ```

### Decision 2: Kafka Relation Pruning
- **Choice**: Fully prune the Kafka relation definitions, config keys, and bindings.
- **Rationale**: Since the Server does not listen to the permissions update ingestion queue (the Listener charm is solely responsible for that), retaining the Kafka relation incurs dead-code overhead and introduces unnecessary security surfaces.

### Decision 3: Pebble Layer Serve Command Mapping
- **Choice**: Retain `SERVICE_NAME` Pebble layer with `"command": "/usr/bin/app serve"`.
- **Rationale**: Keeps the container startup action aligned strictly with the HTTP/gRPC API listener subcommand.

### Decision 4: Migration Ownership and Version/OpenFGA Sharing via `authorization_service_info`
- **Choice**: Only the Server charm carries out database migrations and exposes the `run-migration` action. The Server charm provides the `authorization-service-info` endpoint using `AuthorizationServiceInfoProvider` from `authorization_service_operator_shared.info`.
- **Rationale**: Centralizing migration execution and OpenFGA model creation on the Server prevents race conditions. Dependent components (such as Worker or Listener charms) require `authorization-service-info` to read `workload_version`, `migration_version`, `openfga_store_id`, and `openfga_model_id`. Requirers evaluate these sequentially: if workload version does not match migration version, they enter `WaitingStatus("Waiting for database migration to match workload version")`. If `openfga_store_id` or `openfga_model_id` are missing, they enter `WaitingStatus("Waiting for OpenFGA model from server")`.

## Risks / Trade-offs

- **[Risk] Build dependency missing during local tests or charmcraft pack** → **[Mitigation]**: Define local package overrides inside `pyproject.toml` under `[tool.uv.sources]` pointing to the git repo/branch and include `build-packages: [git]` in `charmcraft.yaml` so `charmcraft pack` build environments have `git` available for `uv`.
- **[Risk] Migration failure or version mismatch across components** → **[Mitigation]**: The Server exclusively triggers migrations via `CommandLine.run_migration()` and records completed versions in `peer_data[MIGRATION_COMPLETED]`. The Server publishes this version over `authorization-service-info`, allowing workers to pause in `WaitingStatus` until migration completes.
