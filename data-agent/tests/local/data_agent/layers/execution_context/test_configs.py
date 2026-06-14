import pytest
from pydantic import ValidationError

import data_agent.layers.execution_context as execution_context_exports
from data_agent.layers.execution_context import DATAExecutionContextLayerConfig


def test_execution_context_package_exports_client_safe_config_symbols_only() -> None:
    assert execution_context_exports.__all__ == [
        "DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID",
        "DATAExecutionContextAgentMode",
        "DATAExecutionContextInvokeFrom",
        "DATAExecutionContextLayerConfig",
        "DATAExecutionContextUserFrom",
    ]
    assert execution_context_exports.DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID == "data.execution_context"
    assert not hasattr(execution_context_exports, "DATAExecutionContextLayer")


def test_execution_context_accepts_real_invoke_from_user_from_and_agent_mode() -> None:
    config = DATAExecutionContextLayerConfig(
        tenant_id="tenant-1",
        user_id="user-1",
        user_from="end-user",
        invoke_from="web-app",
        agent_mode="agent_app",
    )

    assert config.user_from == "end-user"
    assert config.invoke_from == "web-app"
    assert config.agent_mode == "agent_app"


def test_execution_context_rejects_legacy_agent_mode_in_invoke_from() -> None:
    with pytest.raises(ValidationError):
        _ = DATAExecutionContextLayerConfig.model_validate(
            {
                "tenant_id": "tenant-1",
                "user_from": "account",
                "agent_mode": "workflow_run",
                "invoke_from": "workflow_run",
            }
        )


def test_execution_context_layer_config_forbids_runtime_settings_and_unknown_fields() -> None:
    config = DATAExecutionContextLayerConfig(
        tenant_id="tenant-1",
        user_id="user-1",
        user_from="account",
        workflow_id="workflow-1",
        agent_mode="workflow_run",
        invoke_from="service-api",
    )

    assert config.tenant_id == "tenant-1"
    assert config.user_id == "user-1"
    assert config.user_from == "account"
    assert config.workflow_id == "workflow-1"
    assert config.agent_mode == "workflow_run"
    assert config.invoke_from == "service-api"

    with pytest.raises(ValidationError):
        _ = DATAExecutionContextLayerConfig.model_validate(
            {
                "tenant_id": "tenant-1",
                "user_from": "account",
                "agent_mode": "workflow_run",
                "invoke_from": "service-api",
                "daemon_url": "http://daemon",
            }
        )

    with pytest.raises(ValidationError):
        _ = DATAExecutionContextLayerConfig.model_validate(
            {
                "tenant_id": "tenant-1",
                "user_from": "account",
                "agent_mode": "workflow_run",
                "invoke_from": "service-api",
                "unknown": "value",
            }
        )
