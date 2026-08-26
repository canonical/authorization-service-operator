# Shared Library Dependency Specification

## Purpose
Governs the integration and packaging of `authorization-service-operator-shared` dependency across the operator codebase and build system.

## Requirements

### Requirement: Shared library build dependency
The charm SHALL declare a dependency on `authorization-service-operator-shared` in its `pyproject.toml` via PEP 508 direct git URL or `[tool.uv.sources]`, allowing all operator source files to import shared submodules. The charm's `charmcraft.yaml` SHALL include `git` in `build-packages` to ensure `charmcraft pack` can fetch direct Git dependencies during isolated container builds.

#### Scenario: Shared library successfully imported
- **WHEN** the charm's source modules are executed at runtime
- **THEN** they SHALL successfully resolve imports from the `authorization_service_operator_shared` package namespace

#### Scenario: Charmcraft packaging with Git dependency
- **WHEN** `charmcraft pack` executes `uv sync` in a build container
- **THEN** system `git` SHALL be available via `build-packages` to clone and build `authorization-service-operator-shared`
