from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import data_agent.layers.data_plugin as data_plugin_exports
from data_agent.layers.data_plugin import (
    DATAPluginCredentialValue,
    DATAPluginLLMLayerConfig,
    DATAPluginToolCredentialType,
    DATAPluginToolConfig,
    DATAPluginToolParameter,
    DATAPluginToolParameterForm,
    DATAPluginToolParameterType,
    DATAPluginToolsLayerConfig,
    DATAPluginToolValue,
)


def test_data_plugin_package_exports_client_safe_config_symbols_only() -> None:
    assert data_plugin_exports.__all__ == [
        "DATA_PLUGIN_LLM_LAYER_TYPE_ID",
        "DATA_PLUGIN_TOOLS_LAYER_TYPE_ID",
        "DATAPluginCredentialValue",
        "DATAPluginLLMLayerConfig",
        "DATAPluginToolCredentialType",
        "DATAPluginToolConfig",
        "DATAPluginToolOption",
        "DATAPluginToolParameter",
        "DATAPluginToolParameterForm",
        "DATAPluginToolParameterType",
        "DATAPluginToolsLayerConfig",
        "DATAPluginToolValue",
    ]
    assert data_plugin_exports.DATA_PLUGIN_LLM_LAYER_TYPE_ID == "data.plugin.llm"
    assert data_plugin_exports.DATA_PLUGIN_TOOLS_LAYER_TYPE_ID == "data.plugin.tools"
    assert not hasattr(data_plugin_exports, "DATAPluginLLMLayer")


def test_data_plugin_llm_config_accepts_scalar_credentials_and_model_settings() -> None:
    credential: DATAPluginCredentialValue = "secret"
    config = DATAPluginLLMLayerConfig(
        plugin_id="langgenius/openai",
        model_provider="openai",
        model="gpt-4o-mini",
        credentials={"api_key": credential, "enabled": True, "retries": 2, "ratio": 0.5, "empty": None},
        model_settings={"temperature": 0.2, "max_tokens": 64},
    )

    assert config.plugin_id == "langgenius/openai"
    assert config.model_provider == "openai"
    assert config.credentials == {"api_key": "secret", "enabled": True, "retries": 2, "ratio": 0.5, "empty": None}
    assert config.model_settings == {"temperature": 0.2, "max_tokens": 64}
    with pytest.raises(ValidationError):
        _ = DATAPluginLLMLayerConfig.model_validate(
            {
                "plugin_id": "langgenius/openai",
                "model_provider": "openai",
                "model": "gpt-4o-mini",
                "credentials": {"nested": {"not": "allowed"}},
            }
        )


def test_data_plugin_llm_config_rejects_old_provider_field() -> None:
    with pytest.raises(ValidationError):
        _ = DATAPluginLLMLayerConfig.model_validate(
            {
                "provider": "openai",
                "plugin_id": "langgenius/openai",
                "model": "gpt-4o-mini",
            }
        )


def test_data_plugin_tools_layer_config_accepts_prepared_parameters_and_schema() -> None:
    runtime_value: DATAPluginToolValue = {"locale": "en-US", "max_results": 5}
    credential_type: DATAPluginToolCredentialType = "api-key"
    config = DATAPluginToolsLayerConfig(
        tools=[
            DATAPluginToolConfig(
                plugin_id="langgenius/tools",
                provider="search",
                tool_name="web_search",
                credential_type=credential_type,
                name="search_web",
                description="Search the web.",
                credentials={"api_key": "secret"},
                runtime_parameters={"settings": runtime_value},
                parameters=[
                    DATAPluginToolParameter(
                        name="query",
                        type=DATAPluginToolParameterType.STRING,
                        form=DATAPluginToolParameterForm.LLM,
                        required=True,
                        llm_description="Search query",
                    )
                ],
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            )
        ]
    )

    assert config.tools[0].plugin_id == "langgenius/tools"
    assert config.tools[0].provider == "search"
    assert config.tools[0].tool_name == "web_search"
    assert config.tools[0].credential_type == "api-key"
    assert config.tools[0].name == "search_web"
    assert config.tools[0].runtime_parameters == {"settings": {"locale": "en-US", "max_results": 5}}
    assert config.tools[0].parameters[0].name == "query"
    assert config.tools[0].parameters_json_schema["required"] == ["query"]


def test_data_plugin_tool_parameter_accepts_api_tool_parameter_dump_shape() -> None:
    parameter = DATAPluginToolParameter.model_validate(
        {
            "name": "query",
            "label": {"en_US": "Query"},
            "placeholder": None,
            "human_description": {"en_US": "Visible in UI"},
            "type": "select",
            "form": "llm",
            "required": True,
            "default": "data",
            "llm_description": "Search query",
            "input_schema": {"type": "string"},
            "options": [
                {
                    "value": "data",
                    "label": {"en_US": "DATA"},
                }
            ],
        }
    )

    assert parameter.name == "query"
    assert parameter.type is DATAPluginToolParameterType.SELECT
    assert parameter.form is DATAPluginToolParameterForm.LLM
    assert parameter.required is True
    assert parameter.default == "data"
    assert parameter.input_schema == {"type": "string"}
    assert [option.value for option in parameter.options] == ["data"]


def test_data_plugin_tool_parameter_accepts_api_tool_parameter_attributes() -> None:
    parameter = DATAPluginToolParameter.model_validate(
        SimpleNamespace(
            name="language",
            label=SimpleNamespace(en_US="Language"),
            type="string",
            form="form",
            required=False,
            default="en",
            llm_description=None,
            input_schema=None,
            options=[SimpleNamespace(value="en", label=SimpleNamespace(en_US="English"))],
        )
    )

    assert parameter.name == "language"
    assert parameter.type is DATAPluginToolParameterType.STRING
    assert parameter.form is DATAPluginToolParameterForm.FORM
    assert parameter.default == "en"
    assert [option.value for option in parameter.options] == ["en"]


def test_data_plugin_tool_config_rejects_non_json_runtime_parameters() -> None:
    with pytest.raises(ValidationError):
        _ = DATAPluginToolConfig.model_validate(
            {
                "plugin_id": "langgenius/tools",
                "provider": "search",
                "tool_name": "web_search",
                "credential_type": "api-key",
                "runtime_parameters": {"bad": object()},
            }
        )


def test_data_plugin_tool_config_rejects_non_json_schema_values() -> None:
    with pytest.raises(ValidationError):
        _ = DATAPluginToolConfig.model_validate(
            {
                "plugin_id": "langgenius/tools",
                "provider": "search",
                "tool_name": "web_search",
                "credential_type": "api-key",
                "parameters_json_schema": {"type": object()},
            }
        )


def test_data_plugin_tool_config_rejects_strict_flag() -> None:
    with pytest.raises(ValidationError):
        _ = DATAPluginToolConfig.model_validate(
            {
                "plugin_id": "langgenius/tools",
                "provider": "search",
                "tool_name": "web_search",
                "credential_type": "api-key",
                "strict": True,
            }
        )


def test_data_plugin_tool_config_requires_explicit_credential_type() -> None:
    with pytest.raises(ValidationError):
        _ = DATAPluginToolConfig.model_validate(
            {
                "plugin_id": "langgenius/tools",
                "provider": "search",
                "tool_name": "web_search",
            }
        )
