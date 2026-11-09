# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pytest fixtures for integration tests."""

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import jubilant
import pytest

from constants import PEER_INTEGRATION_NAME
from tests.integration.util import APP, get_app_integration_data

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def local_charm() -> Path:
    """Return path to the packed charm, building it if necessary."""
    if charm_path_env := os.getenv("CHARM_PATH"):
        for raw_path in charm_path_env.split(","):
            raw_path = raw_path.strip()
            if not raw_path:
                continue
            path = Path(raw_path)
            if path.exists():
                return path.resolve()
        raise FileNotFoundError(
            f"CHARM_PATH is set to '{charm_path_env}' but no existing file was found"
        )

    if local := next(Path(".").glob("*.charm"), None):
        return local.resolve()

    logger.info("No charm file found — running 'charmcraft pack'")
    try:
        subprocess.run(["charmcraft", "pack"], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Charm build failed: {e}") from e

    if packed := next(Path(".").glob("*.charm"), None):
        return packed.resolve()

    raise RuntimeError("charmcraft pack succeeded but no .charm file was produced")


@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    def _get_data(app_name: str, integration_name: str, unit_num: int = 0) -> dict | None:
        return get_app_integration_data(juju, app_name, integration_name, unit_num)

    return _get_data


@pytest.fixture
def leader_peer_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(APP, PEER_INTEGRATION_NAME)
