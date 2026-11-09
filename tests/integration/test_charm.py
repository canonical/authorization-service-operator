# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the Authorization Service charm."""

import logging
import os
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path

import jubilant
import pytest
import requests

from constants import (
    OPENFGA_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    PG_DATABASE_INTEGRATION_NAME,
)
from tests.integration.util import (
    APP,
    APP_IMAGE,
    DB_APP,
    DB_CHANNEL,
    ISTIO_APP,
    ISTIO_CHANNEL,
    ISTIO_INGRESS_APP,
    OPENFGA_APP,
    OPENFGA_CHANNEL,
    StatusPredicate,
    all_active,
    all_agents_idle,
    and_,
    any_error,
    get_ingress_external_host,
    is_active,
    is_blocked,
    or_,
    remove_integration,
    unit_number,
)

logger = logging.getLogger(__name__)

DEPLOY_TIMEOUT = 10 * 60


@pytest.mark.juju_setup
def test_build_and_deploy(juju: jubilant.Juju, local_charm: Path, tmp_path: Path) -> None:
    """Deploy authorization-service with minimal dependencies, run migration, and assert active."""
    juju.deploy(
        DB_APP,
        channel=DB_CHANNEL,
        trust=True,
    )
    juju.deploy(
        OPENFGA_APP,
        channel=OPENFGA_CHANNEL,
        trust=True,
    )

    logger.info("Fetching Authorization Service image")
    gh_username = os.getenv("GH_USERNAME")
    gh_pat = os.getenv("GH_PAT")

    # Handle the image resource based on environment (GitHub CI/local)
    if gh_username and gh_pat:
        image_resource_path = tmp_path / "image.yaml"
        content = f"registrypath: {APP_IMAGE}\nusername: {gh_username}\npassword: {gh_pat}\n"
        image_resource_path.write_text(content)
        resource = {"oci-image": str(image_resource_path)}
    else:
        resource = {"oci-image": APP_IMAGE}

    juju.deploy(
        local_charm,
        app=APP,
        resources=resource,
        trust=True,
    )

    juju.integrate(f"{APP}:pg-database", f"{DB_APP}:database")
    juju.integrate(f"{OPENFGA_APP}:database", f"{DB_APP}:database")
    juju.integrate(f"{APP}:openfga", f"{OPENFGA_APP}:openfga")

    juju.wait(
        ready=and_(
            all_active(DB_APP, OPENFGA_APP),
            or_(is_active(APP), is_blocked(APP)),
        ),
        error=any_error(APP, DB_APP, OPENFGA_APP),
        timeout=DEPLOY_TIMEOUT,
    )

    juju.run(f"{APP}/0", "run-migration")

    juju.wait(
        ready=all_active(APP, DB_APP, OPENFGA_APP),
        error=any_error(APP, DB_APP, OPENFGA_APP),
        timeout=DEPLOY_TIMEOUT,
    )


def test_istio_ingress_integration(juju: jubilant.Juju) -> None:
    """Deploy the Istio stack and integrate with it."""
    juju.deploy(
        ISTIO_APP,
        channel=ISTIO_CHANNEL,
        trust=True,
    )
    juju.deploy(
        ISTIO_INGRESS_APP,
        channel=ISTIO_CHANNEL,
        trust=True,
    )

    juju.integrate(ISTIO_INGRESS_APP, ISTIO_APP)
    juju.integrate(f"{APP}:ingress", f"{ISTIO_INGRESS_APP}:istio-ingress-route")
    juju.integrate(f"{APP}:forward-auth", f"{ISTIO_INGRESS_APP}:forward-auth")

    juju.wait(
        ready=and_(
            all_active(APP, ISTIO_APP, ISTIO_INGRESS_APP),
            all_agents_idle(APP, ISTIO_APP, ISTIO_INGRESS_APP),
        ),
        error=any_error(APP, ISTIO_APP, ISTIO_INGRESS_APP),
        timeout=DEPLOY_TIMEOUT,
    )


def test_ingress_routing(juju: jubilant.Juju) -> None:
    """Verify HTTP routing via Istio Ingress."""
    try:
        ingress_ip = get_ingress_external_host(juju, app_name=APP)
    except Exception as e:
        pytest.fail(str(e))

    url = f"http://{ingress_ip}/v1/permissions"
    logger.info("Testing endpoint access at %s", url)

    try:
        response = requests.get(url, timeout=5)
    except requests.RequestException as e:
        pytest.fail(f"Failed to connect to Istio Ingress at {url}: {e}")

    assert response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN), (
        f"Expected {HTTPStatus.UNAUTHORIZED} or {HTTPStatus.FORBIDDEN}, "
        f"got {response.status_code}. Response body: {response.text}"
    )


def test_scale_up(
    juju: jubilant.Juju,
    leader_peer_integration_data: dict | None,
    app_integration_data: Callable,
) -> None:
    """Test scaling up the application."""
    target_unit_num = 2
    juju.cli("scale-application", APP, str(target_unit_num))

    juju.wait(
        ready=and_(
            all_active(APP),
            unit_number(APP, target_unit_num),
        ),
        error=any_error(APP),
        timeout=5 * 60,
    )

    follower_peer_data = app_integration_data(APP, PEER_INTEGRATION_NAME, 1)
    assert follower_peer_data
    assert leader_peer_integration_data == follower_peer_data


@pytest.mark.parametrize(
    "remote_app_name,integration_name,endpoint,is_status",
    [
        (DB_APP, PG_DATABASE_INTEGRATION_NAME, "database", is_blocked),
        (OPENFGA_APP, OPENFGA_INTEGRATION_NAME, "openfga", is_blocked),
    ],
)
def test_remove_integration(
    juju: jubilant.Juju,
    remote_app_name: str,
    integration_name: str,
    endpoint: str,
    is_status: Callable[[str], StatusPredicate],
) -> None:
    """Test removing and re-adding mandatory integrations."""
    with remove_integration(juju, remote_app_name, integration_name, endpoint):
        juju.wait(
            ready=is_status(APP),
            error=any_error(APP),
            timeout=DEPLOY_TIMEOUT,
        )


def test_scale_down(juju: jubilant.Juju) -> None:
    """Test scaling down the application."""
    target_unit_num = 1
    juju.cli("scale-application", APP, str(target_unit_num))

    juju.wait(
        ready=and_(
            all_active(APP),
            unit_number(APP, target_unit_num),
        ),
        error=any_error(APP),
        timeout=5 * 60,
    )


@pytest.mark.juju_teardown
def test_remove_application(juju: jubilant.Juju) -> None:
    """Test removing the application."""
    juju.remove_application(APP, destroy_storage=True)
    juju.wait(lambda s: APP not in s.apps, timeout=DEPLOY_TIMEOUT)
