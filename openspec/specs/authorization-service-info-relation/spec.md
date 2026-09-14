# Authorization Service Info Relation Specification

## Purpose
Governs the `authorization-service-info` relation provider interface provided by the Server charm to Worker and Listener requirers.

## Requirements

### Requirement: Authorization Service Info Relation Provider
The Server charm SHALL utilize `authorization_service_operator_shared.info` and declare an `authorization-service-info` provides endpoint in `charmcraft.yaml`.

#### Scenario: Server publishes workload, migration versions, and OpenFGA model parameters
- **WHEN** the Server charm leader unit completes database schema migrations (`self.peer_data[MIGRATION_COMPLETED]`) and creates the OpenFGA authorization model (`self.peer_data[OPENFGA_MODEL_ID]`)
- **THEN** it SHALL publish its `workload_version`, `migration_version`, `openfga_store_id`, and `openfga_model_id` into the `authorization-service-info` application relation databag.

#### Scenario: Provider emits relation ready event
- **WHEN** a dependent charm joins the `authorization-service-info` relation
- **THEN** the `AuthorizationServiceInfoProvider` SHALL emit an `AuthorizationServiceInfoRelationReadyEvent` so the Server charm can immediately evaluate and publish version and OpenFGA store/model information.

### Requirement: Consumer Workload Version and OpenFGA Validation
Requirer charms (such as Workers or Listeners) consuming `authorization-service-info` SHALL evaluate published details sequentially.

#### Scenario: Incomplete migration or version mismatch
- **WHEN** a requirer's local workload version does not match the server's published `migration_version` or if the `authorization-service-info` relation is missing/empty
- **THEN** the requirer SHALL set unit status to `WaitingStatus("Waiting for database migration to match workload version")`.

#### Scenario: Missing OpenFGA store or model parameters
- **WHEN** the server's published `migration_version` matches the requirer's local workload version, BUT `openfga_store_id` or `openfga_model_id` are missing or empty in the relation databag
- **THEN** the requirer SHALL set unit status to `WaitingStatus("Waiting for OpenFGA model from server")`.
