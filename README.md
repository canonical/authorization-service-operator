# Charmed Authorization Service Operator

A Charmed Operator managing the Canonical Authorization Service Server.

## Description

The Authorization Service Operator runs as a Kubernetes workload executing
`/usr/bin/app serve`. It acts as the central policy decision point (PDP) for
the Canonical centralized identity platform, providing fine-grained
authorization, token exchange, and policy evaluation.

On startup, the leader unit executes database schema migrations, creates
OpenFGA authorization models and stores, and publishes database connection
details and migration status to downstream worker and listener charms via
the `authorization-service-info` relation.

## Usage

### Deployment

To deploy the authorization service operator on Kubernetes using Juju:

```bash
juju deploy ./authorization-service*.charm authorization-service \
  --resource oci-image=$(yq eval '.resources.oci-image.upstream-source' charmcraft.yaml) \
  --trust
```

**Note:** The charm and service repositories, as well as the image [registry](http://ghcr.io/canonical/authorization-service), are currently internal.

### Integrations

#### 1. Core Prerequisites (PostgreSQL & OpenFGA)

The charm requires PostgreSQL for persistence and OpenFGA for fine-grained
authorization modeling:

```bash
# Deploy PostgreSQL and OpenFGA
juju deploy postgresql-k8s --channel 14/stable --trust
juju deploy openfga-k8s --channel latest/edge --trust

# Relate to PostgreSQL Database
juju integrate authorization-service:pg-database postgresql-k8s:database
juju integrate openfga-k8s:database postgresql-k8s:database

# Relate to OpenFGA
juju integrate authorization-service:openfga openfga-k8s:openfga
```

#### 2. Secure Token Service (STS)

To enable token exchange and validation, the server must integrate with the Secure Token Service charm.
It is currently not published in the CharmHub store, but can be built from [source](https://github.com/canonical/secure-token-service-operator) using `charmcraft pack`.

```bash
# Deploy Secure Token Service
juju deploy ./secure-token-service*.charm \
  --resource oci-image=$(yq eval '.resources.oci-image.upstream-source' charmcraft.yaml) \
  --trust

# Relate to Secure Token Service
juju integrate authorization-service:sts-info secure-token-service:sts-info
```

**Note:** Secure Token Service requires PostgreSQL, Valkey, Hydra, Istio and CA integrations.
Please refer to the [Secure Token Service Operator README](https://github.com/canonical/secure-token-service-operator/blob/main/README.md) for more details.

#### 3. Ingress & Forward Authentication

To expose the service externally and provide forward authentication to
reverse proxies or ingress controllers:

```bash
# Deploy Istio Ingress
juju deploy istio-k8s --channel dev/edge --trust
juju deploy istio-ingress-k8s --channel dev/edge --trust
juju integrate istio-ingress-k8s istio-k8s

# Relate to Istio Ingress
juju integrate authorization-service:ingress istio-ingress-k8s
juju integrate authorization-service:forward-auth istio-ingress-k8s:forward-auth
```

#### 4. Worker and Listener Charms

The server charm supplies database connection credentials, migration status,
and OpenFGA store/model IDs to downstream worker and listener charms.
You can relate them with the `authorization-service-info` relation:

```bash
# Relate to Authorization Service Server
juju integrate authorization-service:authorization-service-info authorization-service-worker:authorization-service-info
juju integrate authorization-service:authorization-service-info authorization-service-listener:authorization-service-info
```

#### 5. Observability (COS Lite)

Integrate with the Canonical Observability Stack (COS) for logging,
dashboards, and distributed tracing:

```bash
# Relate to Loki for log aggregation
juju integrate authorization-service:logging loki-k8s:logging

# Relate to Grafana for dashboards
juju integrate authorization-service:grafana-dashboard grafana-k8s:grafana-dashboard

# Relate to Tempo for OpenTelemetry tracing
juju integrate authorization-service:tracing tempo-k8s:tracing
```

### Database Migrations

The server charm manages database migrations. On leader startup, pending
database migrations are automatically executed against PostgreSQL. Migrations
can also be manually executed using the `run-migration` action:

```bash
juju run authorization-service/leader run-migration
```

When migrations complete, the server records the migration state in peer
relation data and notifies downstream worker and listener charms via the
`authorization-service-info` relation so they can proceed with their startup.

## License

The Charmed Authorization Service Operator is free software, distributed
under the Apache Software License, version 2.0. See [LICENSE](LICENSE) for
more details.
