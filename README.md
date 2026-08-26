# Charmed Authorization Service Operator

Charmed Operator for Canonical Authorization Service Server.

The Authorization Service provides fine-grained authorization, token exchange, and policy evaluation for the Canonical Identity Platform.

## Relations & Integrations

- **`database`** (`postgresql_client`): PostgreSQL database for service persistence and migration execution.
- **`openfga`** (`openfga`): OpenFGA authorization store and model management.
- **`sts-info`** (`sts-info`): Secure Token Service (STS) integration.
- **`authorization-service-info`** (`authorization-service-info`): Provides workload version, migration status, and OpenFGA store/model IDs to downstream worker and listener charms.
- **`metrics-endpoint`** (`prometheus_scrape`): Prometheus metrics scraping endpoint.
- **`grafana-dashboard`** (`grafana_dashboard`): Grafana dashboard templates.
- **`tracing`** (`tracing`): Tempo OpenTelemetry tracing integration.

## Developer Instructions

### Prerequisites
- `uv` package manager (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `tox` and `tox-uv` for automated environment testing

### Running Unit Tests
```bash
uv pip install -e ../authorization-service-operator-shared
uv run pytest tests/unit  # or tox -e unit
```

### Formatting & Linting
```bash
tox -e lint
```
