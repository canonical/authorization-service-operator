# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration data wrappers for relation-driven workload configuration."""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from charmlibs.interfaces.istio_ingress_route import (
    BackendRef,
    HTTPPathMatch,
    HTTPPathMatchType,
    HTTPRoute,
    HTTPRouteMatch,
    IstioIngressRouteConfig,
    IstioIngressRouteRequirer,
    Listener,
    ProtocolType,
)

from constants import (
    HTTP_PORT,
    INGRESS_HTTP_PORT,
    INGRESS_HTTPS_PORT,
    OPENFGA_MODEL_ID,
    PEER_INTEGRATION_NAME,
    POSTGRESQL_DSN_TEMPLATE,
)
from env_vars import EnvVars

if TYPE_CHECKING:
    from charms.data_platform_libs.v0 import data_interfaces
    from charms.openfga_k8s.v1 import openfga
    from charms.secure_token_service.v0 import sts_info
    from charms.tempo_coordinator_k8s.v0 import tracing
    from ops import CharmBase
    from ops.model import Model

logger = logging.getLogger(__name__)


class PeerData:
    """Access peer relation app-level databag.

    Only the leader unit may write; all units may read.
    Values are JSON-encoded to support non-string types.
    """

    def __init__(self, model: "Model") -> None:
        self._model = model
        self._app = model.app

    def __getitem__(self, key: str) -> Any:
        """Return the JSON-decoded value for *key*, or an empty dict if absent."""
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}
        value = peers.data[self._app].get(key)
        return json.loads(value) if value else {}

    def __setitem__(self, key: str, value: Any) -> None:
        """Write *value* (JSON-encoded) for *key*."""
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            logger.warning(
                "Peer relation %s not found; cannot write key %s", PEER_INTEGRATION_NAME, key
            )
            return
        peers.data[self._app][key] = json.dumps(value)

    def pop(self, key: str) -> Any:
        """Remove and return the value for *key*, or an empty dict if absent."""
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}
        data = peers.data[self._app].pop(key, None)
        return json.loads(data) if data else {}


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Database connection settings for the workload."""

    host: str = ""
    port: str = ""
    dbname: str = ""
    username: str = ""
    password: str = ""

    @property
    def is_ready(self) -> bool:
        """True when all connection fields are populated."""
        return bool(self.host and self.port and self.dbname and self.username and self.password)

    @property
    def dsn(self) -> str:
        """PostgreSQL DSN connection string."""
        return POSTGRESQL_DSN_TEMPLATE.substitute(
            username=self.username,
            password=self.password,
            endpoint=f"{self.host}:{self.port}",
            database=self.dbname,
        )

    def to_env_vars(self) -> EnvVars:
        """Convert the database settings to workload environment variables.

        Returns:
            Environment variables expected by the workload.
        """
        return {
            "POSTGRES_HOST": self.host,
            "POSTGRES_PORT": self.port,
            "POSTGRES_USER": self.username,
            "POSTGRES_PASSWORD": self.password,
            "POSTGRES_DB": self.dbname,
        }

    @classmethod
    def load(cls, requirer: "data_interfaces.DatabaseRequires") -> "DatabaseConfig":
        """Load database settings from the database relation.

        Args:
            requirer: Database relation requirer helper.

        Returns:
            A populated database configuration, or an empty one when the
            relation is not yet established.
        """
        if not requirer.relations:
            return cls()

        integration_id = requirer.relations[0].id
        integration_data: dict[str, str] = requirer.fetch_relation_data()[integration_id]

        endpoint = integration_data.get("endpoints", "").split(",")[0]
        host, _, port = endpoint.rpartition(":")
        return cls(
            host=host,
            port=port,
            dbname=requirer.database,
            username=integration_data.get("username", ""),
            password=integration_data.get("password", ""),
        )


@dataclass(frozen=True, slots=True)
class OpenFGAIntegrationData:
    """OpenFGA client settings for the workload."""

    url: str = ""
    api_token: str = ""
    store_id: str = ""

    @property
    def api_scheme(self) -> str:
        """URL scheme (e.g. ``http`` or ``https``)."""
        return urlparse(self.url).scheme

    @property
    def api_host(self) -> str:
        """Host and port portion of the URL."""
        return urlparse(self.url).netloc

    def to_env_vars(self) -> EnvVars:
        """Convert the OpenFGA settings to workload environment variables.

        Returns:
            Environment variables expected by the workload.
        """
        return {
            "OPENFGA_STORE_ID": self.store_id,
            "OPENFGA_API_TOKEN": self.api_token,
            "OPENFGA_API_SCHEME": self.api_scheme,
            "OPENFGA_API_HOST": self.api_host,
        }


@dataclass(frozen=True, slots=True)
class OpenFGAModelData:
    """OpenFGA authorization model settings for the workload."""

    model_id: str = ""

    def to_env_vars(self) -> EnvVars:
        """Convert the OpenFGA model settings to workload environment variables.

        Returns:
            Environment variables expected by the workload.
        """
        return {"OPENFGA_AUTHZ_MODEL_ID": self.model_id}

    @classmethod
    def load(cls, source: dict) -> "OpenFGAModelData":
        """Load the OpenFGA model data from a peer data dict.

        Args:
            source: Dict (typically from peer app databag) keyed by
                :data:`constants.OPENFGA_MODEL_ID`.

        Returns:
            A populated instance, or an empty one when the key is absent.
        """
        return cls(model_id=source.get(OPENFGA_MODEL_ID, ""))


class OpenFGAIntegration:
    """Wrapper around :class:`OpenFGARequires` for structured data access."""

    def __init__(self, integration_requirer: "openfga.OpenFGARequires") -> None:
        self._openfga_requirer = integration_requirer

    def is_store_ready(self) -> bool:
        """Return True when the OpenFGA store is provisioned and the store ID is available."""
        provider_data = self._openfga_requirer.get_store_info()
        return provider_data is not None and provider_data.store_id is not None

    @property
    def openfga_integration_data(self) -> OpenFGAIntegrationData:
        """Current OpenFGA integration data, falling back to defaults."""
        if not (provider_data := self._openfga_requirer.get_store_info()):
            return OpenFGAIntegrationData()

        return OpenFGAIntegrationData(
            url=provider_data.http_api_url,
            api_token=provider_data.token,
            store_id=provider_data.store_id,
        )


@dataclass(frozen=True, slots=True)
class TracingConfig:
    """Tracing exporter settings for the workload."""

    otlp_endpoint: str = ""

    def to_env_vars(self) -> EnvVars:
        """Convert the tracing settings to workload environment variables.

        Returns:
            Environment variables expected by the workload, or an empty dict
            when tracing is not configured.
        """
        if not self.otlp_endpoint:
            return {}
        return {
            "TELEMETRY_ENABLED": True,
            "OTEL_EXPORTER_OTLP_ENDPOINT": self.otlp_endpoint,
        }

    @classmethod
    def load(cls, requirer: "tracing.TracingEndpointRequirer") -> "TracingConfig":
        """Load tracing settings from the tracing relation.

        Args:
            requirer: Tracing relation requirer helper.

        Returns:
            A tracing configuration, or a default one when tracing is not ready.
        """
        if not requirer.is_ready():
            return cls()

        endpoint = requirer.get_endpoint("otlp_http")
        if not endpoint:
            return cls()

        return cls(otlp_endpoint=endpoint)


@dataclass(frozen=True, slots=True)
class StsConfig:
    """Secure Token Service settings for the workload."""

    jwks_url: str = ""
    grpc_address: str = ""
    tls_enabled: bool = False

    def to_env_vars(self) -> EnvVars:
        """Convert the STS settings to workload environment variables.

        Returns:
            Environment variables expected by the workload, or an empty dict
            when STS is not configured.
        """
        if not self.jwks_url:
            return {}
        return {
            "EXTAUTHZ_JWK_SET_URL": self.jwks_url,
            "STS_ADDRESS": self.grpc_address,
            "STS_USE_TLS": str(self.tls_enabled).lower(),
        }

    @classmethod
    def load(cls, requirer: "sts_info.StsInfoRequirer") -> "StsConfig":
        """Load STS settings from the sts-info relation.

        Args:
            requirer: STS relation requirer helper.

        Returns:
            A STS configuration, or a default one when the relation is not ready.
        """
        try:
            sts_info = requirer.get_sts_info()
        except Exception:
            return cls()

        return cls(
            jwks_url=sts_info.jwks_url,
            grpc_address=sts_info.grpc_address,
            tls_enabled=sts_info.tls_enabled,
        )


class IstioIngressIntegration:
    """Encapsulates the Istio Gateway API configuration for HTTP ingress."""

    def __init__(self, charm: "CharmBase", relation_name: str) -> None:
        self.requirer = IstioIngressRouteRequirer(charm, relation_name=relation_name)
        self.app_name = charm.app.name
        self.model_name = charm.model.name

    @property
    def external_url(self) -> str | None:
        """Public URL if provided by the Istio gateway."""
        if not self.requirer.external_host:
            return None
        scheme = "https" if self.requirer.tls_enabled else "http"
        return f"{scheme}://{self.requirer.external_host}"

    def submit_routes(self) -> None:
        """Compile and submit HTTP routes to the Istio Ingress Gateway.

        Routes ``/v1`` prefix traffic to the authorization-service REST API.
        """
        ingress_port = INGRESS_HTTPS_PORT if self.requirer.tls_enabled else INGRESS_HTTP_PORT
        http_listener = Listener(port=ingress_port, protocol=ProtocolType.HTTP)
        config = IstioIngressRouteConfig(
            model=self.model_name,
            listeners=[http_listener],
            http_routes=[
                HTTPRoute(
                    name="authz-http-route",
                    listener=http_listener,
                    matches=[
                        HTTPRouteMatch(
                            path=HTTPPathMatch(type=HTTPPathMatchType.PathPrefix, value="/v1")
                        ),
                    ],
                    backends=[BackendRef(service=self.app_name, port=HTTP_PORT)],
                )
            ],
        )
        self.requirer.submit_config(config)
