import pytest
from pydantic import ValidationError
from pydantic_ai.messages import FinalResultEvent

from agenton.compositor import CompositorSessionSnapshot
from agenton.layers import ExitIntent
from agenton_collections.layers.plain import PLAIN_PROMPT_LAYER_TYPE_ID, PromptLayerConfig
import data_agent.protocol as protocol_exports
from data_agent.layers.ask_human import DATAAskHumanLayerConfig
from data_agent.layers.execution_context import DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID, DATAExecutionContextLayerConfig
from data_agent.layers.data_plugin import DATA_PLUGIN_LLM_LAYER_TYPE_ID, DATA_PLUGIN_TOOLS_LAYER_TYPE_ID
from data_agent.layers.output import DATA_OUTPUT_LAYER_TYPE_ID, DATAOutputLayerConfig
from data_agent.protocol import DATA_AGENT_HISTORY_LAYER_ID, DATA_AGENT_MODEL_LAYER_ID, DATA_AGENT_OUTPUT_LAYER_ID
from data_agent.protocol.schemas import (
    RUN_EVENT_ADAPTER,
    CreateRunRequest,
    DeferredToolCallPayload,
    LayerExitSignals,
    PydanticAIStreamRunEvent,
    RunCancelledEvent,
    RunCancelledEventData,
    RunComposition,
    RunFailedEvent,
    RunFailedEventData,
    RunLayerSpec,
    RunStartedEvent,
    RunSucceededEvent,
    RunSucceededEventData,
    normalize_composition,
)
from data_agent.layers.data_plugin.configs import (
    DATAPluginLLMLayerConfig,
    DATAPluginToolConfig,
    DATAPluginToolParameter,
    DATAPluginToolParameterForm,
    DATAPluginToolParameterType,
    DATAPluginToolsLayerConfig,
)


def test_run_event_adapter_round_trips_typed_variants() -> None:
    events = [
        RunStartedEvent(run_id="run-1"),
        PydanticAIStreamRunEvent(run_id="run-1", data=FinalResultEvent(tool_name=None, tool_call_id=None)),
        RunSucceededEvent(
            run_id="run-1",
            data=RunSucceededEventData(
                output={"answer": ["done"]},
                session_snapshot=CompositorSessionSnapshot(layers=[]),
            ),
        ),
        RunSucceededEvent(
            run_id="run-2",
            data=RunSucceededEventData(
                deferred_tool_call=DeferredToolCallPayload(
                    tool_call_id="tool-call-1",
                    tool_name="ask_human",
                    args={"question": "Need approval"},
                    metadata={"layer_type": "data.ask_human"},
                ),
                session_snapshot=CompositorSessionSnapshot(layers=[]),
            ),
        ),
        RunFailedEvent(run_id="run-1", data=RunFailedEventData(error="boom", reason="shutdown")),
        RunCancelledEvent(run_id="run-1", data=RunCancelledEventData(reason="user_cancelled")),
    ]

    for event in events:
        payload = RUN_EVENT_ADAPTER.dump_json(event)
        decoded = RUN_EVENT_ADAPTER.validate_json(payload)

        assert decoded.type == event.type
        assert decoded.run_id == event.run_id


def test_pydantic_ai_event_data_uses_agent_stream_event_model() -> None:
    event = RUN_EVENT_ADAPTER.validate_python(
        {
            "run_id": "run-1",
            "type": "pydantic_ai_event",
            "data": {"event_kind": "final_result", "tool_name": None, "tool_call_id": None},
        }
    )

    assert isinstance(event, PydanticAIStreamRunEvent)
    assert isinstance(event.data, FinalResultEvent)


def test_create_run_request_rejects_old_compositor_payload_and_model_layer_id_is_public() -> None:
    assert DATA_AGENT_MODEL_LAYER_ID == "llm"
    assert DATA_AGENT_HISTORY_LAYER_ID == "history"
    assert DATA_AGENT_OUTPUT_LAYER_ID == "output"
    with pytest.raises(ValidationError):
        _ = CreateRunRequest.model_validate(
            {
                "compositor": {"layers": []},
            }
        )


def test_protocol_package_no_longer_exports_execution_context_dto() -> None:
    assert not hasattr(protocol_exports, "ExecutionContext")


def test_create_run_request_accepts_dto_first_public_composition_and_normalizes_graph_config() -> None:
    prompt_config = PromptLayerConfig(prefix="system", user="hello")
    execution_context_config = DATAExecutionContextLayerConfig(
        tenant_id="tenant-1",
        user_from="account",
        workflow_id="workflow-1",
        workflow_run_id="workflow-run-1",
        node_id="node-1",
        node_execution_id="node-execution-1",
        agent_mode="workflow_run",
        invoke_from="service-api",
        trace_id="trace-1",
    )
    llm_config = DATAPluginLLMLayerConfig(
        plugin_id="langgenius/openai",
        model_provider="openai",
        model="demo-model",
        credentials={"api_key": "secret"},
    )
    output_config = DATAOutputLayerConfig(
        json_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        }
    )
    request = CreateRunRequest(
        purpose="workflow_node",
        idempotency_key="workflow-run-1:node-execution-1",
        metadata={"source": "unit_test"},
        composition=RunComposition(
            layers=[
                RunLayerSpec(name="prompt", type=PLAIN_PROMPT_LAYER_TYPE_ID, config=prompt_config),
                RunLayerSpec(
                    name="execution_context",
                    type=DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
                    config=execution_context_config,
                ),
                RunLayerSpec(
                    name=DATA_AGENT_MODEL_LAYER_ID,
                    type=DATA_PLUGIN_LLM_LAYER_TYPE_ID,
                    deps={"execution_context": "execution_context"},
                    config=llm_config,
                ),
                RunLayerSpec(
                    name=DATA_AGENT_OUTPUT_LAYER_ID,
                    type=DATA_OUTPUT_LAYER_TYPE_ID,
                    config=output_config,
                ),
            ]
        ),
    )

    graph_config, layer_configs = normalize_composition(request.composition)
    payload = request.model_dump(mode="json")

    assert payload["composition"]["layers"][1]["config"] == {
        "tenant_id": "tenant-1",
        "user_id": None,
        "user_from": "account",
        "app_id": None,
        "workflow_id": "workflow-1",
        "workflow_run_id": "workflow-run-1",
        "node_id": "node-1",
        "node_execution_id": "node-execution-1",
        "conversation_id": None,
        "agent_id": None,
        "agent_config_version_id": None,
        "agent_mode": "workflow_run",
        "invoke_from": "service-api",
        "trace_id": "trace-1",
    }
    assert payload["purpose"] == "workflow_node"
    assert payload["idempotency_key"] == "workflow-run-1:node-execution-1"
    assert payload["metadata"] == {"source": "unit_test"}
    assert payload["composition"]["layers"][0]["config"] == {"prefix": "system", "user": "hello", "suffix": []}
    assert [layer.model_dump(mode="json") for layer in graph_config.layers] == [
        {"name": "prompt", "type": PLAIN_PROMPT_LAYER_TYPE_ID, "deps": {}, "metadata": {}},
        {
            "name": "execution_context",
            "type": DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
            "deps": {},
            "metadata": {},
        },
        {
            "name": DATA_AGENT_MODEL_LAYER_ID,
            "type": DATA_PLUGIN_LLM_LAYER_TYPE_ID,
            "deps": {"execution_context": "execution_context"},
            "metadata": {},
        },
        {
            "name": DATA_AGENT_OUTPUT_LAYER_ID,
            "type": DATA_OUTPUT_LAYER_TYPE_ID,
            "deps": {},
            "metadata": {},
        },
    ]
    assert layer_configs == {
        "prompt": prompt_config,
        "execution_context": execution_context_config,
        DATA_AGENT_MODEL_LAYER_ID: llm_config,
        DATA_AGENT_OUTPUT_LAYER_ID: output_config,
    }


def test_create_run_request_accepts_deferred_tool_results_payload() -> None:
    request = CreateRunRequest.model_validate(
        {
            "composition": {
                "layers": [
                    {"name": "prompt", "type": PLAIN_PROMPT_LAYER_TYPE_ID, "config": {"user": "hello"}},
                    {"name": "ask_human", "type": "data.ask_human", "config": DATAAskHumanLayerConfig().model_dump()},
                ]
            },
            "deferred_tool_results": {
                "calls": {
                    "tool-call-1": {
                        "status": "submitted",
                        "action": {"id": "submit", "label": "Submit"},
                        "values": {"comment": "Looks good."},
                    }
                }
            },
        }
    )

    assert request.deferred_tool_results is not None
    assert request.deferred_tool_results.calls["tool-call-1"] == {
        "status": "submitted",
        "action": {"id": "submit", "label": "Submit"},
        "values": {"comment": "Looks good."},
    }


def test_create_run_request_accepts_plugin_tools_layer_with_prepared_parameters_and_schema() -> None:
    request = CreateRunRequest.model_validate(
        {
            "composition": {
                "layers": [
                    {"name": "prompt", "type": PLAIN_PROMPT_LAYER_TYPE_ID, "config": {"user": "hello"}},
                    {
                        "name": "execution_context",
                        "type": DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
                        "config": {
                            "tenant_id": "tenant-1",
                            "user_from": "account",
                            "agent_mode": "workflow_run",
                            "invoke_from": "service-api",
                        },
                    },
                    {
                        "name": DATA_AGENT_MODEL_LAYER_ID,
                        "type": DATA_PLUGIN_LLM_LAYER_TYPE_ID,
                        "deps": {"execution_context": "execution_context"},
                        "config": {
                            "plugin_id": "langgenius/openai",
                            "model_provider": "openai",
                            "model": "demo-model",
                            "credentials": {"api_key": "secret"},
                        },
                    },
                    {
                        "name": "tools",
                        "type": DATA_PLUGIN_TOOLS_LAYER_TYPE_ID,
                        "deps": {"execution_context": "execution_context"},
                        "config": {
                            "tools": [
                                {
                                    "plugin_id": "langgenius/search",
                                    "provider": "search",
                                    "tool_name": "web_search",
                                    "credential_type": "api-key",
                                    "runtime_parameters": {"site": "docs.data.ai"},
                                    "parameters": [
                                        {
                                            "name": "query",
                                            "type": "string",
                                            "form": "llm",
                                            "required": True,
                                            "llm_description": "Search query",
                                        },
                                        {
                                            "name": "site",
                                            "type": "string",
                                            "form": "form",
                                            "required": True,
                                            "llm_description": "Hidden site",
                                        },
                                    ],
                                    "parameters_json_schema": {
                                        "type": "object",
                                        "properties": {"query": {"type": "string", "description": "Search query"}},
                                        "required": ["query"],
                                    },
                                }
                            ]
                        },
                    },
                ]
            }
        }
    )

    graph_config, layer_configs = normalize_composition(request.composition)

    assert [layer.type for layer in graph_config.layers] == [
        PLAIN_PROMPT_LAYER_TYPE_ID,
        DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
        DATA_PLUGIN_LLM_LAYER_TYPE_ID,
        DATA_PLUGIN_TOOLS_LAYER_TYPE_ID,
    ]
    assert DATAPluginToolsLayerConfig.model_validate(layer_configs["tools"]) == DATAPluginToolsLayerConfig(
        tools=[
            DATAPluginToolConfig(
                plugin_id="langgenius/search",
                provider="search",
                tool_name="web_search",
                credential_type="api-key",
                runtime_parameters={"site": "docs.data.ai"},
                parameters=[
                    DATAPluginToolParameter(
                        name="query",
                        type=DATAPluginToolParameterType.STRING,
                        form=DATAPluginToolParameterForm.LLM,
                        required=True,
                        llm_description="Search query",
                    ),
                    DATAPluginToolParameter(
                        name="site",
                        type=DATAPluginToolParameterType.STRING,
                        form=DATAPluginToolParameterForm.FORM,
                        required=True,
                        llm_description="Hidden site",
                    ),
                ],
                parameters_json_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            )
        ]
    )


def test_on_exit_default_to_suspend_and_are_public() -> None:
    assert protocol_exports.LayerExitSignals is LayerExitSignals
    assert protocol_exports.RunComposition is RunComposition
    assert protocol_exports.RunLayerSpec is RunLayerSpec
    assert protocol_exports.normalize_composition is normalize_composition
    assert protocol_exports.DATA_AGENT_OUTPUT_LAYER_ID == DATA_AGENT_OUTPUT_LAYER_ID
    request = CreateRunRequest.model_validate({"composition": {"layers": []}})

    assert request.on_exit.default is ExitIntent.SUSPEND
    assert request.on_exit.layers == {}


def test_run_succeeded_event_data_requires_exactly_one_result_variant() -> None:
    snapshot = CompositorSessionSnapshot(layers=[])

    with pytest.raises(ValidationError, match="Exactly one of output or deferred_tool_call must be set"):
        _ = RunSucceededEventData(session_snapshot=snapshot)

    with pytest.raises(ValidationError, match="Exactly one of output or deferred_tool_call must be set"):
        _ = RunSucceededEventData(
            output="done",
            deferred_tool_call=DeferredToolCallPayload(
                tool_call_id="tool-call-1",
                tool_name="ask_human",
                args={"question": "Need approval"},
            ),
            session_snapshot=snapshot,
        )


def test_run_succeeded_event_data_allows_explicit_json_null_output() -> None:
    snapshot = CompositorSessionSnapshot(layers=[])

    data = RunSucceededEventData(output=None, session_snapshot=snapshot)

    assert data.output is None
    assert data.deferred_tool_call is None


def test_run_succeeded_event_round_trips_explicit_json_null_output() -> None:
    event = RunSucceededEvent(
        run_id="run-null-output",
        data=RunSucceededEventData(output=None, session_snapshot=CompositorSessionSnapshot(layers=[])),
    )

    payload = RUN_EVENT_ADAPTER.dump_json(event)
    decoded = RUN_EVENT_ADAPTER.validate_json(payload)

    assert isinstance(decoded, RunSucceededEvent)
    assert decoded.data.output is None
    assert decoded.data.deferred_tool_call is None
    assert b'"output":null' in payload
    assert b'"deferred_tool_call"' not in payload


def test_on_exit_accept_layer_overrides() -> None:
    request = CreateRunRequest.model_validate(
        {
            "composition": {"layers": []},
            "on_exit": {
                "default": "delete",
                "layers": {"prompt": "suspend", "llm": "delete"},
            },
        }
    )

    assert request.on_exit.default is ExitIntent.DELETE
    assert request.on_exit.layers == {"prompt": ExitIntent.SUSPEND, "llm": ExitIntent.DELETE}


def test_create_run_request_rejects_removed_top_level_execution_context() -> None:
    with pytest.raises(ValidationError):
        _ = CreateRunRequest.model_validate(
            {
                "composition": {"layers": []},
                "execution_context": {
                    "tenant_id": "tenant-1",
                    "user_from": "account",
                    "agent_mode": "workflow_run",
                    "invoke_from": "service-api",
                },
            }
        )


def test_layer_exit_signals_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _ = LayerExitSignals.model_validate({"default": "suspend", "unknown": "value"})


@pytest.mark.parametrize("event_type", ["agent_output", "session_snapshot"])
def test_removed_non_terminal_payload_events_are_rejected(event_type: str) -> None:
    with pytest.raises(ValidationError):
        _ = RUN_EVENT_ADAPTER.validate_python({"run_id": "run-1", "type": event_type, "data": {}})
