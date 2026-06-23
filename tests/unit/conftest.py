# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared fixtures for charm unit tests."""

from typing import Any
from unittest.mock import PropertyMock

import pytest
from ops import ActiveStatus, testing
from pytest_mock import MockerFixture

from constants import (
    CONTAINER_NAME,
    FORWARD_AUTH_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    OPENFGA_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    PG_DATABASE_INTEGRATION_NAME,
    STS_INFO_INTEGRATION_NAME,
    TRACING_INTEGRATION_NAME,
)
from integrations import OpenFGAIntegrationData

APP_NAME = "authorization-service"
MODEL_NAME = "testing"

OPENFGA_INTEGRATION_DATA = OpenFGAIntegrationData(
    url="http://openfga.internal:8080",
    store_id="store-abc",
    api_token="api-key",
)


@pytest.fixture
def mock_openfga_ready(mocker: MockerFixture) -> None:
    """Mock the OpenFGA integration as store-ready with model available."""
    mocker.patch("integrations.OpenFGAIntegration.is_store_ready", return_value=True)
    mocker.patch(
        "integrations.OpenFGAIntegration.openfga_integration_data",
        new_callable=PropertyMock,
        return_value=OPENFGA_INTEGRATION_DATA,
    )
    mocker.patch("charm.AuthorizationServiceCharm._ensure_openfga_model", return_value=True)


@pytest.fixture(autouse=True)
def mocked_k8s_resource_patch(mocker: MockerFixture) -> None:
    """Prevent KubernetesComputeResourcesPatch from making real K8s API calls."""
    mocker.patch(
        "charms.observability_libs.v0.kubernetes_compute_resources_patch.ResourcePatcher",
        autospec=True,
    )
    mocker.patch.multiple(
        "charm.KubernetesComputeResourcesPatch",
        _namespace="testing",
        _patch=lambda *a, **kw: None,
        is_ready=lambda *a, **kw: True,
        get_status=lambda *a, **kw: ActiveStatus(),
    )


@pytest.fixture(autouse=True)
def mocked_log_forwarder(mocker: MockerFixture) -> None:
    """Prevent LogForwarder from checking Juju version."""
    mocker.patch(
        "charms.loki_k8s.v1.loki_push_api._PebbleLogClient.check_juju_version",
        return_value=None,
    )


def create_state(
    *,
    leader: bool = True,
    can_connect: bool = True,
    config: dict[str, Any] | None = None,
    relations: list[testing.Relation] | None = None,
    secrets: list[testing.Secret] | None = None,
    extra_execs: list[testing.Exec] | None = None,
) -> testing.State:
    """Factory for building a testing.State with sensible defaults.

    Args:
        leader: Whether the unit is the leader.
        can_connect: Whether the workload container is connectable.
        config: Charm configuration dict.
        relations: List of active relations.
        secrets: Juju secrets.
        extra_execs: Additional Exec mocks beyond the default version command.

    Returns:
        A fully configured State object.
    """
    default_execs: list[testing.Exec] = []
    if can_connect:
        default_execs.append(
            testing.Exec(["/usr/bin/app", "version"], return_code=0, stdout="0.2.1\n")
        )
        default_execs.append(
            testing.Exec(
                ["/usr/bin/app", "migrate", "status"],
                return_code=0,
                stdout="up-to-date\n",
            )
        )

    if extra_execs:
        default_execs.extend(extra_execs)

    container = testing.Container(
        name=CONTAINER_NAME,
        can_connect=can_connect,
        execs=set(default_execs),
    )

    return testing.State(
        containers=[container],
        config=config or {},
        leader=leader,
        model=testing.Model(name=MODEL_NAME),
        relations=[testing.PeerRelation(endpoint=PEER_INTEGRATION_NAME), *(relations or [])],
        secrets=secrets or [],
    )


@pytest.fixture
def peer_relation() -> testing.PeerRelation:
    """Provide the authorization-service peer relation."""
    return testing.PeerRelation(endpoint=PEER_INTEGRATION_NAME)


# ---------------------------------------------------------------------------
# Relation fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def database_relation() -> testing.Relation:
    """Provide a fully-configured pg-database relation."""
    return testing.Relation(
        endpoint=PG_DATABASE_INTEGRATION_NAME,
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "data": '{"database": "authorization_service"}',
            "database": "authorization_service",
            "endpoints": "pg.internal:5432",
            "username": "cerberus_user",
            "password": "cerberus_pass",
        },
    )


@pytest.fixture
def openfga_relation() -> testing.Relation:
    """Provide a fully-configured openfga relation."""
    return testing.Relation(
        endpoint=OPENFGA_INTEGRATION_NAME,
        interface="openfga",
        remote_app_name="openfga-k8s",
        remote_app_data={
            "grpc_api_url": "grpc://openfga.internal:8081",
            "http_api_url": "http://openfga.internal:8080",
            "store_id": "store-abc-123",
            "token": "openfga-api-key",
            "token_secret_id": "",
        },
    )


@pytest.fixture
def sts_relation() -> testing.Relation:
    """Provide a sts-info relation with data."""
    return testing.Relation(
        endpoint=STS_INFO_INTEGRATION_NAME,
        interface="sts_info",
        remote_app_name="secure-token-service",
        remote_app_data={
            "http_address": "http://sts.internal:8080",
            "grpc_address": "sts.internal:9090",
            "jwks_set_url": "https://sts.internal/.well-known/jwks.json",
            "tls_enabled": "true",
        },
    )


@pytest.fixture
def tracing_relation() -> testing.Relation:
    """Provide a tracing relation."""
    return testing.Relation(
        endpoint=TRACING_INTEGRATION_NAME,
        interface="tracing",
        remote_app_name="tempo-k8s",
        remote_app_data={
            "receivers": '[{"protocol": {"name": "otlp_http", "type": "http"}, "url": "http://tempo:4318"}]'
        },
    )


@pytest.fixture
def ingress_relation() -> testing.Relation:
    """Provide an ingress relation."""
    return testing.Relation(
        endpoint=INGRESS_INTEGRATION_NAME,
        interface="istio_ingress_route",
        remote_app_name="istio-ingress-k8s",
        remote_app_data={
            "external_host": "authz.example.com",
            "tls_enabled": "True",
        },
    )


@pytest.fixture
def forward_auth_relation() -> testing.Relation:
    """Provide a forward-auth relation (authorization-service is the provider)."""
    return testing.Relation(
        endpoint=FORWARD_AUTH_INTEGRATION_NAME,
        interface="forward_auth",
        remote_app_name="istio-ingress-k8s",
    )
