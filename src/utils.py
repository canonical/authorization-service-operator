# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from constants import (
    CONTAINER_NAME,
    OPENFGA_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    PG_DATABASE_INTEGRATION_NAME,
)

if TYPE_CHECKING:
    from charm import AuthorizationServiceCharm

logger = logging.getLogger(__name__)

CharmEventHandler = TypeVar("CharmEventHandler", bound=Callable[..., Any])
Condition = Callable[["AuthorizationServiceCharm"], bool]


def leader_unit(func: CharmEventHandler) -> CharmEventHandler:
    """Decorator that ensures the handler only runs on the leader unit."""

    @wraps(func)
    def wrapper(charm: "AuthorizationServiceCharm", *args: Any, **kwargs: Any) -> Any | None:
        if not charm.unit.is_leader():
            return None
        return func(charm, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def integration_existence(name: str) -> "Condition":
    """Create a condition that checks whether a relation exists."""

    def wrapped(charm: "AuthorizationServiceCharm") -> bool:
        return bool(charm.model.relations[name])

    return wrapped


database_integration_exists = integration_existence(PG_DATABASE_INTEGRATION_NAME)
openfga_integration_exists = integration_existence(OPENFGA_INTEGRATION_NAME)
peer_integration_exists = integration_existence(PEER_INTEGRATION_NAME)


def container_connectivity(charm: "AuthorizationServiceCharm") -> bool:
    """Check if the workload container is reachable."""
    return charm.unit.get_container(CONTAINER_NAME).can_connect()


def openfga_store_readiness(charm: "AuthorizationServiceCharm") -> bool:
    """Check if the OpenFGA store is ready."""
    return charm.openfga_integration.is_store_ready()
