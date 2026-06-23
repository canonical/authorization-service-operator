## Purpose

This capability governs the integration with the Secure Token Service (STS) via the `sts-info` relation. It allows the Authorization Service to discover the STS endpoint and JWKS URL at runtime rather than relying on static configuration, enabling the `EXTAUTHZ_JWK_SET_URL`, `STS_ADDRESS`, and `STS_USE_TLS` environment variables to be sourced dynamically from the live relation data.

## ADDED Requirements

### Requirement: Charm consumes STS endpoint info to configure the workload
The charm SHALL consume the `sts-info` relation (interface: `charms.secure_token_service.v0.sts_info`, provider: `secure-token-service`) via `StsInfoRequirer`. When joined and data is available, `StsConfig.to_env_vars()` SHALL supply `EXTAUTHZ_JWK_SET_URL`, `STS_ADDRESS`, and `STS_USE_TLS` to the Pebble layer.

The `StsInfoRequirer` is instantiated in `charm.py` `__init__`. The charm SHALL observe `StsInfoRelationUpdatedEvent` and call `_on_holistic_handler()` in response.

`StsConfig` SHALL be a `@dataclass(frozen=True, slots=True)` wrapping the data from `StsInfoRequirer.get_sts_info()`:

| Field | Source (`StsInfoData`) | Env var |
|---|---|---|
| `jwks_set_url` | `StsInfoData.jwks_set_url` | `EXTAUTHZ_JWK_SET_URL` |
| `grpc_address` | `StsInfoData.grpc_address` | `STS_ADDRESS` |
| `tls_enabled` | `StsInfoData.tls_enabled` | `STS_USE_TLS` |

> **Do not modify `lib/charms/secure_token_service/v0/sts_info.py`.** Only the requirer side is used.

#### Scenario: STS relation provides all required fields
- **WHEN** the `sts-info` relation is joined and the provider publishes `grpc_address`, `jwks_set_url`, and `tls_enabled`
- **THEN** `StsConfig.to_env_vars()` returns `{"EXTAUTHZ_JWK_SET_URL": ..., "STS_ADDRESS": ..., "STS_USE_TLS": ...}`
- **AND** `_on_holistic_handler()` re-applies the Pebble layer with the STS env vars included

#### Scenario: STS relation is absent
- **WHEN** no `sts-info` relation is present
- **THEN** `_sts_config` is `None` and no STS env vars are injected into the Pebble layer
- **AND** the unit does NOT enter `BlockedStatus` solely due to missing `sts-info`

#### Scenario: STS relation is broken
- **WHEN** the `sts-info` `relation_broken` event fires
- **THEN** `_on_holistic_handler()` is called, removing STS env vars from the next layer
