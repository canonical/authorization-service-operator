# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm state unit tests using ops.testing."""

import json

import ops
import pytest
from authorization_service_operator_shared.database import DatabaseConfig
from authorization_service_operator_shared.exceptions import WorkloadError
from authorization_service_operator_shared.observability import TracingConfig
from authorization_service_operator_shared.sts import StsConfig
from conftest import MODEL_NAME, create_state
from ops import testing
from pytest_mock import MockerFixture

from charm import AuthorizationServiceCharm
from constants import GRPC_PORT, MIGRATION_COMPLETED, OPENFGA_MODEL_ID

CHARM_TYPE = AuthorizationServiceCharm
CTX = testing.Context(CHARM_TYPE)

DB_CONFIG = DatabaseConfig(
    host="pg.internal",
    port="5432",
    dbname="authorization_service",
    username="authz_user",
    password="authz_pass",
)

STS_CONFIG = StsConfig(
    jwks_url="https://sts.internal/jwks",
    grpc_address="sts.internal:9090",
    tls_enabled=True,
)

TRACING_CONFIG = TracingConfig(otlp_endpoint="tempo:4317")


# ---------------------------------------------------------------------------
# 11.2  pebble_ready — all required integrations present → ActiveStatus
# ---------------------------------------------------------------------------


def test_pebble_ready_all_present_yields_active(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )

    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(
        CTX.on.pebble_ready(container=state.get_container("authorization-service")),
        state,
    )
    assert out.unit_status == ops.ActiveStatus()


# ---------------------------------------------------------------------------
# 11.3  pebble_ready — missing pg-database → BlockedStatus
# ---------------------------------------------------------------------------


def test_pebble_ready_missing_database_yields_blocked(
    mock_openfga_ready: None,
    openfga_relation: testing.Relation,
) -> None:
    state = create_state(relations=[openfga_relation])
    out = CTX.run(
        CTX.on.pebble_ready(container=state.get_container("authorization-service")),
        state,
    )
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 11.4  pebble_ready — missing openfga → BlockedStatus
# ---------------------------------------------------------------------------


def test_pebble_ready_missing_openfga_yields_blocked(
    mocker: MockerFixture,
    database_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )

    state = create_state(relations=[database_relation])
    out = CTX.run(
        CTX.on.pebble_ready(container=state.get_container("authorization-service")),
        state,
    )
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 11.6  config_changed — invalid log_level → BlockedStatus
# ---------------------------------------------------------------------------


def test_config_changed_invalid_log_level_yields_blocked() -> None:
    state = create_state(config={"log_level": "INVALID_LEVEL"})
    out = CTX.run(CTX.on.config_changed(), state)
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 11.6b  collect_unit_status — peer integration missing → WaitingStatus
# ---------------------------------------------------------------------------


def test_collect_status_missing_peer_integration_yields_waiting(
    mocker: MockerFixture,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    # Use State directly without the peer relation auto-added by create_state.
    # Both DB and OpenFGA relations are present so their BlockedStatuses do not
    # overshadow the peer WaitingStatus check.
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch("charm.OpenFGARelationHandler.is_ready", return_value=True)
    container = testing.Container(
        name="authorization-service",
        can_connect=True,
        execs={
            testing.Exec(["/usr/bin/app", "version"], return_code=0, stdout="0.2.1\n"),
            testing.Exec(
                ["/usr/bin/app", "migrate", "status"], return_code=0, stdout="up-to-date\n"
            ),
        },
    )
    state = testing.State(
        containers=[container],
        config={},
        leader=True,
        model=testing.Model(name="testing"),
        relations=[database_relation, openfga_relation],  # no peer relation
    )
    out = CTX.run(CTX.on.config_changed(), state)
    assert isinstance(out.unit_status, ops.WaitingStatus)
    assert "peer" in out.unit_status.message.lower()


# ---------------------------------------------------------------------------
# 11.7  config_changed — valid config + all integrations → pebble layer applied
# ---------------------------------------------------------------------------


def test_config_changed_valid_applies_pebble_layer(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )

    state = create_state(
        config={"log_level": "debug"},
        relations=[database_relation, openfga_relation],
    )
    out = CTX.run(CTX.on.config_changed(), state)
    container = out.get_container("authorization-service")
    # Service should be defined in the plan
    assert "authorization-service" in container.plan.services


# ---------------------------------------------------------------------------
# 11.8  database_relation_broken → BlockedStatus
# ---------------------------------------------------------------------------


def test_database_relation_broken_yields_blocked(
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(CTX.on.relation_broken(database_relation), state)
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 11.9  openfga_relation_broken → BlockedStatus
# ---------------------------------------------------------------------------


def test_openfga_relation_broken_yields_blocked(
    mocker: MockerFixture,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(CTX.on.relation_broken(openfga_relation), state)
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 11.10  tracing_relation_changed → TELEMETRY_ENABLED in env
# ---------------------------------------------------------------------------


def test_tracing_relation_changed_sets_telemetry_enabled(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
    tracing_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )

    state = create_state(relations=[database_relation, openfga_relation, tracing_relation])
    out = CTX.run(CTX.on.relation_changed(tracing_relation), state)

    container = out.get_container("authorization-service")
    env = container.plan.services["authorization-service"].environment
    assert env.get("TELEMETRY_ENABLED") == "true"
    assert env.get("OTEL_EXPORTER_OTLP_ENDPOINT") == "tempo:4317"
    assert env.get("OTEL_SERVICE_NAME") == "authorization-service"
    assert env.get("METRICS_ENABLED") == "true"
    assert env.get("METRICS_PORT") == "9100"
    assert env.get("METRICS_PATH") == "/metrics"


def test_tracing_relation_missing_protocol_on_non_leader(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    empty_tracing_relation = testing.Relation(
        endpoint="tracing",
        interface="tracing",
        remote_app_name="tempo-coordinator-k8s",
        remote_app_data={"receivers": "[]"},
    )
    peer_relation = testing.PeerRelation(
        endpoint="authorization-service-peers",
        interface="authorization_service_peers",
        local_app_data={
            MIGRATION_COMPLETED: '"0.2.1"',
            f"{OPENFGA_MODEL_ID}_0.2.1": '"model-xyz"',
        },
    )
    state = create_state(
        leader=False,
        peer_relation=peer_relation,
        relations=[database_relation, openfga_relation, empty_tracing_relation],
    )
    out = CTX.run(CTX.on.relation_changed(empty_tracing_relation), state)

    container = out.get_container("authorization-service")
    env = container.plan.services["authorization-service"].environment
    assert env.get("TELEMETRY_ENABLED") == "false"
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env


def test_metrics_endpoint_relation_publishes_scrape_jobs_and_alerts(
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    metrics_relation = testing.Relation(
        endpoint="metrics-endpoint",
        interface="prometheus_scrape",
        remote_app_name="prometheus-k8s",
    )
    state = create_state(
        leader=True,
        relations=[database_relation, openfga_relation, metrics_relation],
    )
    out = CTX.run(CTX.on.relation_joined(metrics_relation), state)

    rel_out = out.get_relation(metrics_relation.id)
    scrape_jobs = json.loads(rel_out.local_app_data["scrape_jobs"])
    assert scrape_jobs == [
        {"metrics_path": "/metrics", "static_configs": [{"targets": ["*:9100"]}]}
    ]
    alert_rules = json.loads(rel_out.local_app_data["alert_rules"])
    alert_names = {
        rule["alert"] for group in alert_rules.get("groups", []) for rule in group.get("rules", [])
    }
    assert "AuthorizationServiceUnavailable-multiple" in alert_names
    assert "AuthorizationServiceUnavailable-all" in alert_names


def test_logging_relation_configures_log_forwarding(
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    logging_relation = testing.Relation(
        endpoint="logging",
        interface="loki_push_api",
        remote_app_name="loki-k8s",
        remote_units_data={
            0: {"endpoint": '{"url": "http://loki:3100/loki/api/v1/push"}'},
        },
    )
    state = create_state(
        leader=True,
        relations=[database_relation, openfga_relation, logging_relation],
    )
    out = CTX.run(CTX.on.relation_changed(logging_relation), state)

    container = out.get_container("authorization-service")
    assert "authorization-service-log-forwarding" in container.layers
    rel_out = out.get_relation(logging_relation.id)
    alert_rules = json.loads(rel_out.local_app_data["alert_rules"])
    alert_names = {
        rule["alert"] for group in alert_rules.get("groups", []) for rule in group.get("rules", [])
    }
    assert "HighFrequencyHighSeverityLog" in alert_names


# ---------------------------------------------------------------------------
# 11.11  upgrade_charm — no migration needed → ActiveStatus
# ---------------------------------------------------------------------------


def test_upgrade_charm_no_migration_needed_yields_active(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch("charm.CommandLine.migrate_status", return_value=False)

    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(CTX.on.upgrade_charm(), state)
    assert out.unit_status == ops.ActiveStatus()


# ---------------------------------------------------------------------------
# 11.12  upgrade_charm — migration pending → BlockedStatus
# ---------------------------------------------------------------------------


def test_upgrade_charm_migration_pending_yields_blocked(
    mocker: MockerFixture,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch("charm.CommandLine.migrate_status", return_value=True)

    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(CTX.on.upgrade_charm(), state)
    assert isinstance(out.unit_status, ops.BlockedStatus)
    assert "migration" in out.unit_status.message.lower()


# ---------------------------------------------------------------------------
# 11.13  upgrade_charm — migrate_status raises WorkloadError → proceeds to holistic
# ---------------------------------------------------------------------------


def test_upgrade_charm_migrate_status_raises_proceeds_to_holistic(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch("charm.CommandLine.migrate_status", side_effect=WorkloadError("fail"))
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )

    state = create_state(relations=[database_relation, openfga_relation])
    out = CTX.run(CTX.on.upgrade_charm(), state)
    # WorkloadError on migrate_status falls back to False; holistic handler runs
    assert out.unit_status == ops.ActiveStatus()


# ---------------------------------------------------------------------------
# 11.14  sts_info_relation_updated — STS env vars in layer
# ---------------------------------------------------------------------------


def test_sts_relation_updated_sets_sts_env_vars(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
    sts_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch(
        "charm.STSRelationHandler.get_env_vars",
        return_value={
            "EXTAUTHZ_JWK_SET_URL": "https://sts.internal/jwks",
            "STS_ADDRESS": "sts.internal:9090",
            "STS_USE_TLS": "false",
        },
    )

    state = create_state(relations=[database_relation, openfga_relation, sts_relation])
    out = CTX.run(CTX.on.relation_changed(sts_relation), state)

    container = out.get_container("authorization-service")
    env = container.plan.services["authorization-service"].environment
    assert "EXTAUTHZ_JWK_SET_URL" in env
    assert "STS_ADDRESS" in env
    assert "STS_USE_TLS" in env


# ---------------------------------------------------------------------------
# 11.15  sts relation broken → STS vars absent; still Active
# ---------------------------------------------------------------------------


def test_sts_relation_broken_removes_sts_vars_stays_active(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
    sts_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch(
        "authorization_service_operator_shared.sts.StsConfig.load", return_value=StsConfig()
    )  # gone after break

    state = create_state(relations=[database_relation, openfga_relation, sts_relation])
    out = CTX.run(CTX.on.relation_broken(sts_relation), state)

    assert out.unit_status == ops.ActiveStatus()
    container = out.get_container("authorization-service")
    env = container.plan.services["authorization-service"].environment
    assert "EXTAUTHZ_JWK_SET_URL" not in env


# ---------------------------------------------------------------------------
# 11.16  forward-auth relation created → ForwardAuthProvider publishes config
# ---------------------------------------------------------------------------


def test_forward_auth_config_published_on_relation_created(
    mocker: MockerFixture,
    forward_auth_relation: testing.Relation,
) -> None:
    update_mock = mocker.patch(
        "charms.oauth2_proxy_k8s.v0.forward_auth.ForwardAuthProvider._update_relation_data",
    )

    state = create_state(relations=[forward_auth_relation])
    CTX.run(CTX.on.relation_created(forward_auth_relation), state)

    update_mock.assert_called()
    config = update_mock.call_args[0][0]
    assert config is not None
    expected_address = f"grpc://authorization-service.{MODEL_NAME}.svc.cluster.local:{GRPC_PORT}"
    assert config.decisions_address == expected_address
    assert "authorization-service" in config.app_names


# ---------------------------------------------------------------------------
# 11.18  patch_failed → BlockedStatus
# ---------------------------------------------------------------------------


def test_resource_patch_failed_yields_blocked(mocker: MockerFixture) -> None:
    mocker.patch.multiple(
        "charm.KubernetesComputeResourcesPatch",
        _namespace="testing",
        _patch=lambda *a, **kw: None,
        is_ready=lambda *a, **kw: False,
        get_status=lambda *a, **kw: ops.BlockedStatus("Resource patch failed"),
    )

    state = create_state()
    out = CTX.run(CTX.on.config_changed(), state)
    assert isinstance(out.unit_status, ops.BlockedStatus)


# ---------------------------------------------------------------------------
# 9a.3  run-migration action tests
# ---------------------------------------------------------------------------


def test_run_migration_action_leader_success(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    migrate_mock = mocker.patch("charm.CommandLine.run_migration", return_value=None)
    peer_setitem = mocker.patch(
        "authorization_service_operator_shared.peer.PeerData.__setitem__", return_value=None
    )

    state = create_state(
        leader=True,
        relations=[database_relation, openfga_relation],
    )
    out = CTX.run(CTX.on.action("run-migration"), state)

    migrate_mock.assert_called_once_with(DB_CONFIG.dsn)
    peer_setitem.assert_called_once_with(MIGRATION_COMPLETED, mocker.ANY)
    assert out.unit_status == ops.ActiveStatus()


def test_run_migration_action_non_leader_fails() -> None:
    state = create_state(leader=False)
    with pytest.raises(testing.ActionFailed) as exc_info:
        CTX.run(CTX.on.action("run-migration"), state)
    assert "leader" in exc_info.value.message.lower()


def test_run_migration_action_workload_error_calls_fail(
    mocker: MockerFixture,
    database_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch("charm.CommandLine.run_migration", side_effect=WorkloadError("DB error"))

    state = create_state(leader=True, relations=[database_relation])
    with pytest.raises(testing.ActionFailed) as exc_info:
        CTX.run(CTX.on.action("run-migration"), state)
    assert "DB error" in exc_info.value.message


def test_authorization_service_info_relation_publishes_data(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    info_relation = testing.Relation(
        endpoint="authorization-service-info",
        interface="authorization_service_info",
    )
    peer_relation = testing.PeerRelation(
        endpoint="authorization-service-peers",
        interface="authorization_service_peers",
        local_app_data={MIGRATION_COMPLETED: '"0.1.0"'},
    )

    state = create_state(
        leader=True,
        peer_relation=peer_relation,
        relations=[database_relation, openfga_relation, info_relation],
    )
    out = CTX.run(
        CTX.on.relation_joined(info_relation),
        state,
    )

    out_rel = out.get_relation(info_relation.id)
    assert out_rel.local_app_data.get("migration_version") == "0.1.0"


def test_openfga_model_id_version_lookup(
    mocker: MockerFixture,
    mock_openfga_ready: None,
    database_relation: testing.Relation,
    openfga_relation: testing.Relation,
) -> None:
    mocker.patch(
        "authorization_service_operator_shared.database.DatabaseConfig.load",
        return_value=DB_CONFIG,
    )
    mocker.patch("charm.CommandLine.get_service_version", return_value="1.2.0")
    peer_relation = testing.PeerRelation(
        endpoint="authorization-service-peers",
        interface="authorization_service_peers",
        local_app_data={
            f"{OPENFGA_MODEL_ID}_1.2.0": '"model_v120"',
        },
    )

    state = create_state(
        leader=True,
        peer_relation=peer_relation,
        relations=[database_relation, openfga_relation],
    )
    out = CTX.run(
        CTX.on.pebble_ready(container=state.get_container("authorization-service")),
        state,
    )
    container = out.get_container("authorization-service")
    env = container.plan.services["authorization-service"].environment
    assert env["OPENFGA_AUTHORIZATION_MODEL_ID"] == "model_v120"
