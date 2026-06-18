# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the Authorization Service charm."""

import logging
from pathlib import Path

import jubilant
import pytest

from tests.integration.util import (
    APP,
    APP_IMAGE,
    DB_APP,
    DB_CHANNEL,
    any_error,
    is_blocked,
)

logger = logging.getLogger(__name__)

DEPLOY_TIMEOUT = 10 * 60


@pytest.mark.juju_setup
def test_deploy(juju: jubilant.Juju, local_charm: Path) -> None:
    """Deploy authorization-service with postgresql-k8s; assert the charm reaches BlockedStatus."""
    juju.deploy(
        DB_APP,
        channel=DB_CHANNEL,
        trust=True,
    )

    juju.deploy(
        local_charm,
        app=APP,
        resources={"oci-image": APP_IMAGE},
        trust=True,
    )

    juju.integrate(f"{APP}:pg-database", DB_APP)

    juju.wait(
        ready=is_blocked(APP),
        error=any_error(DB_APP),
        timeout=DEPLOY_TIMEOUT,
    )
