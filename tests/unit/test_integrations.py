# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for src/integrations.py."""

from unittest.mock import MagicMock

from authorization_service_operator_shared.database import DatabaseConfig
from authorization_service_operator_shared.ingress import IstioIngressIntegration
from authorization_service_operator_shared.observability import TracingConfig
from authorization_service_operator_shared.openfga import OpenFGAConfig as OpenFGAIntegrationData
from authorization_service_operator_shared.sts import StsConfig
from charmlibs.interfaces.istio_ingress_route import IstioIngressRouteConfig
from charms.secure_token_service.v0.sts_info import (
    StsInfoRelationDataMissingError,
    StsInfoRelationMissingError,
)

from constants import INGRESS_HTTP_PORT, INGRESS_HTTPS_PORT

# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------


def _make_database_requirer(data: dict | None = None) -> MagicMock:
    requirer = MagicMock()
    if data is None:
        requirer.relations = []
    else:
        relation = MagicMock()
        relation.id = 1
        requirer.relations = [relation]
        requirer.fetch_relation_data.return_value = {1: data}
        requirer.database = data.get("database", "")
    return requirer


class TestDatabaseConfig:
    def test_load_returns_empty_when_no_relation(self):
        requirer = _make_database_requirer()
        config = DatabaseConfig.load(requirer)
        assert not config.is_ready

    def test_load_returns_config_on_valid_data(self):
        requirer = _make_database_requirer({
            "endpoints": "db.example.com:5432",
            "username": "authz_user",
            "password": "secret",
            "database": "authorization_service",
        })
        config = DatabaseConfig.load(requirer)
        assert config.is_ready
        assert config.host == "db.example.com"
        assert config.port == "5432"
        assert config.username == "authz_user"
        assert config.password == "secret"
        assert config.dbname == "authorization_service"

    def test_load_handles_malformed_endpoint(self):
        requirer = _make_database_requirer({
            "endpoints": "no-port-here",
            "username": "u",
            "password": "p",
            "database": "db",
        })
        config = DatabaseConfig.load(requirer)
        assert config.host == ""
        assert config.port == "no-port-here"

    def test_load_returns_empty_for_missing_fields(self):
        requirer = _make_database_requirer({
            "endpoints": "db.example.com:5432",
            "username": "",
            "password": "secret",
            "database": "authz",
        })
        config = DatabaseConfig.load(requirer)
        assert not config.is_ready

    def test_to_env_vars_returns_expected_keys(self):
        config = DatabaseConfig(
            host="db.host",
            port="5432",
            dbname="authz",
            username="user",
            password="pass",
        )
        env = config.to_env_vars()
        assert env["POSTGRES_HOST"] == "db.host"
        assert env["POSTGRES_PORT"] == "5432"
        assert env["POSTGRES_DB"] == "authz"
        assert env["POSTGRES_USER"] == "user"
        assert env["POSTGRES_PASSWORD"] == "pass"


# ---------------------------------------------------------------------------
# OpenFGAIntegration
# ---------------------------------------------------------------------------


def _make_openfga_requirer(store_info=None) -> MagicMock:
    requirer = MagicMock()
    requirer.get_store_info.return_value = store_info
    return requirer


def _make_store_info(
    http_api_url: str = "http://openfga:8080",
    store_id: str = "store-123",
    token: str = "api-key",
) -> MagicMock:
    info = MagicMock()
    info.http_api_url = http_api_url
    info.store_id = store_id
    info.token = token
    return info


class TestOpenFGAIntegration:
    def test_to_env_vars_returns_expected_keys(self):
        data = OpenFGAIntegrationData(
            address="http://openfga:8080",
            store_id="store-abc",
            token="tok",
        )
        env = data.to_env_vars()
        assert env["OPENFGA_ADDRESS"] == "http://openfga:8080"
        assert env["OPENFGA_STORE_ID"] == "store-abc"
        assert env["OPENFGA_API_KEY"] == "tok"


# ---------------------------------------------------------------------------
# TracingConfig
# ---------------------------------------------------------------------------


def _make_tracing_requirer(
    ready: bool = True, endpoint: str | None = "http://tempo:4318"
) -> MagicMock:
    requirer = MagicMock()
    requirer.is_ready.return_value = ready
    requirer.get_endpoint.return_value = endpoint
    return requirer


class TestTracingConfig:
    def test_load_returns_default_when_not_ready(self):
        assert TracingConfig.load(_make_tracing_requirer(ready=False)) == TracingConfig()

    def test_load_returns_default_when_no_endpoint(self):
        assert TracingConfig.load(_make_tracing_requirer(endpoint=None)) == TracingConfig()

    def test_load_returns_config_on_valid_data(self):
        config = TracingConfig.load(_make_tracing_requirer())
        assert config is not None
        assert config.otlp_endpoint == "http://tempo:4318"

    def test_to_env_vars_sets_telemetry_enabled(self):
        config = TracingConfig(otlp_endpoint="http://tempo:4318")
        env = config.to_env_vars()
        assert env["TELEMETRY_ENABLED"] == "true"
        assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://tempo:4318"


# ---------------------------------------------------------------------------
# StsConfig
# ---------------------------------------------------------------------------


def _make_sts_requirer(
    *,
    raise_error: type[Exception] | None = None,
    jwks_url: str = "https://sts.example.com/.well-known/jwks.json",
    grpc_address: str = "sts.example.com:9090",
    tls_enabled: bool = True,
) -> MagicMock:
    requirer = MagicMock()
    if raise_error is not None:
        # StsInfoRelationMissingError takes no args; others take a message
        if raise_error is StsInfoRelationMissingError:
            requirer.get_sts_info.side_effect = raise_error()
        else:
            requirer.get_sts_info.side_effect = raise_error("test error")
    else:
        sts_data = MagicMock()
        sts_data.jwks_url = jwks_url
        sts_data.grpc_address = grpc_address
        sts_data.tls_enabled = tls_enabled
        requirer.get_sts_info.return_value = sts_data
    return requirer


class TestStsConfig:
    def test_load_returns_default_on_relation_missing_error(self):
        requirer = _make_sts_requirer(raise_error=StsInfoRelationMissingError)
        assert StsConfig.load(requirer) == StsConfig()

    def test_load_returns_default_on_any_sts_relation_error(self):
        requirer = _make_sts_requirer(raise_error=StsInfoRelationDataMissingError)
        assert StsConfig.load(requirer) == StsConfig()

    def test_load_returns_config_on_valid_data(self):
        requirer = _make_sts_requirer()
        config = StsConfig.load(requirer)
        assert config is not None
        assert config.jwks_url == "https://sts.example.com/.well-known/jwks.json"
        assert config.grpc_address == "sts.example.com:9090"
        assert config.tls_enabled is True

    def test_to_env_vars_returns_expected_keys(self):
        config = StsConfig(
            jwks_url="https://sts.example.com/jwks",
            grpc_address="sts:9090",
            tls_enabled=True,
        )
        env = config.to_env_vars()
        assert env["EXTAUTHZ_JWK_SET_URL"] == "https://sts.example.com/jwks"
        assert env["STS_ADDRESS"] == "sts:9090"
        assert env["STS_USE_TLS"] == "true"

    def test_to_env_vars_tls_disabled(self):
        config = StsConfig(
            jwks_url="http://sts.example.com/jwks",
            grpc_address="sts:9090",
            tls_enabled=False,
        )
        assert config.to_env_vars()["STS_USE_TLS"] == "false"


# ---------------------------------------------------------------------------
# IstioIngressIntegration
# ---------------------------------------------------------------------------


def _make_ingress_charm(
    app_name: str = "authorization-service",
    model_name: str = "test-model",
    external_host: str = "",
    tls_enabled: bool = False,
) -> MagicMock:
    charm = MagicMock()
    charm.app.name = app_name
    charm.model.name = model_name
    requirer = MagicMock()
    requirer.external_host = external_host
    requirer.tls_enabled = tls_enabled
    charm._mock_requirer = requirer
    return charm


class TestIstioIngressIntegration:
    def _make_integration(self, **kwargs) -> IstioIngressIntegration:
        charm = _make_ingress_charm(**kwargs)
        integration = IstioIngressIntegration.__new__(IstioIngressIntegration)
        integration.requirer = charm._mock_requirer
        integration.app_name = charm.app.name
        integration.model_name = charm.model.name
        return integration

    def test_external_url_none_when_no_host(self):
        integration = self._make_integration()
        assert integration.external_url is None

    def test_external_url_http_when_tls_disabled(self):
        integration = self._make_integration(external_host="authz.example.com", tls_enabled=False)
        assert integration.external_url == "http://authz.example.com"

    def test_external_url_https_when_tls_enabled(self):
        integration = self._make_integration(external_host="authz.example.com", tls_enabled=True)
        assert integration.external_url == "https://authz.example.com"

    def test_submit_routes_uses_http_port_when_tls_disabled(self):
        integration = self._make_integration(tls_enabled=False)
        integration.submit_routes()
        config = integration.requirer.submit_config.call_args[0][0]
        assert isinstance(config, IstioIngressRouteConfig)
        assert len(config.http_routes) == 1
        route = config.http_routes[0]
        assert route.matches[0].path.value == "/v1"
        assert config.listeners[0].port == INGRESS_HTTP_PORT

    def test_submit_routes_uses_https_port_when_tls_enabled(self):
        integration = self._make_integration(tls_enabled=True)
        integration.submit_routes()
        config = integration.requirer.submit_config.call_args[0][0]
        assert isinstance(config, IstioIngressRouteConfig)
        assert config.listeners[0].port == INGRESS_HTTPS_PORT
