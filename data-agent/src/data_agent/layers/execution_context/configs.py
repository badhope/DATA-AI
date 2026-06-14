"""Client-safe DTOs for the DATA execution-context Agenton layer.

This layer carries both DATA product execution context (tenant, user, workflow,
invoke source) and Agent backend runtime mode. The product-facing fields are
used by trusted server-side boundaries such as the Agent Stub when they
need to reconstruct DATA API file-access scope without granting the sandbox any
direct inner-API credentials. Server-only plugin-daemon settings are injected
by the runtime provider factory and therefore do not appear in this public
schema.
"""

from typing import ClassVar, Final, Literal, TypeAlias

from pydantic import ConfigDict

from agenton.layers import LayerConfig


DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID: Final[str] = "data.execution_context"
DATAExecutionContextAgentMode: TypeAlias = Literal[
    "workflow_run",
    "single_step",
    "agent_app",
    "babysit",
    "fasten",
]
DATAExecutionContextUserFrom: TypeAlias = Literal["account", "end-user"]
DATAExecutionContextInvokeFrom: TypeAlias = Literal[
    "service-api",
    "openapi",
    "web-app",
    "trigger",
    "explore",
    "debugger",
    "published",
    "validation",
]


class DATAExecutionContextLayerConfig(LayerConfig):
    """Public config for DATA execution identity and daemon transport context."""

    tenant_id: str
    user_id: str | None = None
    user_from: DATAExecutionContextUserFrom
    app_id: str | None = None
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    node_id: str | None = None
    node_execution_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    agent_config_version_id: str | None = None
    agent_mode: DATAExecutionContextAgentMode
    invoke_from: DATAExecutionContextInvokeFrom
    trace_id: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


__all__ = [
    "DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID",
    "DATAExecutionContextAgentMode",
    "DATAExecutionContextInvokeFrom",
    "DATAExecutionContextUserFrom",
    "DATAExecutionContextLayerConfig",
]
