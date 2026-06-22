## Purpose

This capability governs how the Authorization Service REST API is exposed externally. It covers the ingress route configuration submitted to `istio-ingress-k8s` via the `charmlibs.interfaces.istio_ingress_route` interface, and the downstream `forward-auth` integration that enables Istio to delegate authorization decisions to the Authorization Service.

## ADDED Requirements

### Requirement: Charm provides an ingress relation to expose the service
The charm SHALL declare a `requires` ingress relation endpoint using the `charmlibs.interfaces.istio_ingress_route` interface (Python package: `charmlibs-interfaces-istio-ingress-route`), provided by `istio-ingress-k8s`, to route external traffic to the Authorization Service REST API.

Ingress integration is encapsulated in an `IstioIngressIntegration` class in `src/integrations.py`. This class wraps `IstioIngressRouteRequirer` and exposes:
- `external_url: str | None` — constructs `https://host` or `http://host` based on `requirer.tls_enabled`
- `submit_routes()` — builds and submits an `IstioIngressRouteConfig` to the provider

The charm SHALL observe `istio_ingress.requirer.on.ready` and call `submit_routes()` in the handler.

#### Scenario: Ingress relation is established
- **WHEN** the ingress relation is joined and the provider publishes `external_host`
- **THEN** the charm calls `submit_routes()` to publish route config
- **AND** reads the external URL and logs it

#### Scenario: Ingress relation is not established
- **WHEN** no ingress relation is present
- **THEN** the charm continues to operate normally
- **AND** the unit status is NOT set to `BlockedStatus` solely due to missing ingress

### Requirement: Ingress submits HTTP routes for the REST API
The charm SHALL submit an `IstioIngressRouteConfig` with:
- A single `Listener` at `INGRESS_HTTPS_PORT` (443) when TLS is enabled, or `INGRESS_HTTP_PORT` (80) otherwise, with `ProtocolType.HTTP`
- A single `HTTPRoute` matching path prefix `/v1` with a `BackendRef(service=self.app_name, port=HTTP_PORT)` (port 8070)

The `/v1` prefix covers all PermissionsService REST endpoints (`POST /v1/permissions`, `GET /v1/permissions`, `GET /v1/permissions/{service_id}`, `DELETE /v1/permissions/{service_id}`).

Constants in `src/constants.py`:
```python
INGRESS_HTTP_PORT = 80
INGRESS_HTTPS_PORT = 443
```

### Requirement: Charm provides forward-auth for Istio mesh authorization
The charm SHALL declare a `provides` `forward-auth` relation endpoint using the `charms.oauth2_proxy_k8s.v0.forward_auth` interface (`ForwardAuthProvider`). The Authorization Service acts as the provider: Istio (via `istio-ingress-k8s`) is the requirer and delegates `envoy.service.auth.v3.Authorization/Check` calls to the Authorization Service gRPC endpoint.

The `ForwardAuthProvider` SHALL be instantiated with a static `ForwardAuthConfig` at charm `__init__` time:
```python
ForwardAuthConfig(
    # grpc:// scheme is used so urlparse() on the istio side correctly extracts hostname and port
    decisions_address=f"grpc://{self.app.name}.{self.model.name}.svc.cluster.local:{GRPC_PORT}",
    app_names=[self.app.name],
)
```

The `forward-auth` relation is optional. Its absence SHALL NOT cause `BlockedStatus`.

#### Scenario: forward-auth relation created → config is published
- **WHEN** the `forward-auth` relation is created
- **THEN** `ForwardAuthProvider` publishes the config to the relation databag
- **AND** `decisions_address` is `grpc://<app>.<model>.svc.cluster.local:9091`
- **AND** `app_names` contains the application name
