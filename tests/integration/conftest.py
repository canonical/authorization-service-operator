# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pytest fixtures for integration tests."""

import logging
import os
import subprocess
from pathlib import Path

import pytest

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
