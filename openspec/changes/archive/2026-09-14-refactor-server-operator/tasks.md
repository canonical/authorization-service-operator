## 1. Build & Dependency Integration

- [x] 1.1 Declare dependency on `authorization-service-operator-shared` in `pyproject.toml` using PEP 508 git direct URL and `[tool.uv.sources]` overrides.
- [x] 1.2 Configure `charmcraft.yaml` with `build-packages: [git]` under the `charm` part so `charmcraft pack` can fetch git dependencies during builds.
- [x] 1.3 Cleanly delete local redundant codebase files: `src/cli.py`, `src/configs.py`, `src/services.py`, `src/exceptions.py`, `src/utils.py`, and `src/env_vars.py`.

## 2. Manifest & Configuration Cleanup (Kafka Pruning)

- [x] 2.1 Remove Kafka relation endpoints (`requires`/`provides`) from `charmcraft.yaml` (or `metadata.yaml`).
- [x] 2.2 Remove Kafka configuration keys from `config.yaml` and internal charm config models.

## 3. Charm Reconciliation Loop Refactor

- [x] 3.1 Update `src/charm.py` to import decorators, configurations, and exception hierarchies directly from `authorization_service_operator_shared`.
- [x] 3.2 Refactor relation handling in `src/charm.py` to leverage `DatabaseRelationHandler`, `OpenFGARelationHandler`, and `STSRelationHandler` from the shared library, fully stripping out Kafka event handlers.
- [x] 3.3 Ensure database schema migrations via `CommandLine.run_migration()` are retained exclusively on the Server charm in `src/charm.py` on leader unit initialization.
- [x] 3.4 Implement `authorization_service_operator_shared.info` module and register `authorization-service-info` provides endpoint in `charmcraft.yaml`.
- [x] 3.5 Publish `workload_version`, database `migration_version` (`self.peer_data[MIGRATION_COMPLETED]`), `openfga_store_id`, and `openfga_model_id` (`self.peer_data[OPENFGA_MODEL_ID]`) via `AuthorizationServiceInfoProvider` in `src/charm.py`.
- [x] 3.6 Update container service planning inside `src/charm.py` to utilize `PebbleService` and `WorkloadService` from the shared package, ensuring the command is set to `/usr/bin/app serve` on HTTP (8070) and gRPC (9091) ports.

## 4. Testing & Code Quality

- [x] 4.1 Refactor table-driven unit test specifications in `tests/unit/test_charm.py` to mock the shared package namespace and remove stale Kafka test cases.
- [x] 4.2 Execute static code checks and verify formatting compliance across all remaining operator source files using `ruff`.
