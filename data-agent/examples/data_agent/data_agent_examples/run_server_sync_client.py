"""Synchronous Python client example for the DATA Agent run server.

Requires the same running FastAPI server as the async examples. Before starting
that server, sync the server runtime dependencies with
`uv sync --project data-agent --extra server` or install
`data-agent[server]`. ``create_run_sync`` does not retry ``POST /runs``; if a
timeout occurs, inspect server state or create a new run explicitly rather than
assuming the original request was not accepted.
"""

from agenton_collections.layers.plain import PLAIN_PROMPT_LAYER_TYPE_ID, PromptLayerConfig
from data_agent.client import Client
from data_agent.layers.execution_context import DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID, DATAExecutionContextLayerConfig
from data_agent.layers.data_plugin import (
    DATA_PLUGIN_LLM_LAYER_TYPE_ID,
    DATAPluginCredentialValue,
    DATAPluginLLMLayerConfig,
)
from data_agent.protocol import DATA_AGENT_MODEL_LAYER_ID, CreateRunRequest, RunComposition, RunLayerSpec


API_BASE_URL = "http://localhost:8000"
TENANT_ID = "replace-with-tenant-id"
PLUGIN_ID = "langgenius/openai"
PLUGIN_PROVIDER = "openai"
MODEL_NAME = "gpt-4o-mini"
MODEL_CREDENTIALS: dict[str, DATAPluginCredentialValue] = {"api_key": "replace-with-provider-key"}


def main() -> None:
    with Client(base_url=API_BASE_URL) as client:
        run = client.create_run_sync(
            CreateRunRequest(
                composition=RunComposition(
                    layers=[
                        RunLayerSpec(
                            name="prompt",
                            type=PLAIN_PROMPT_LAYER_TYPE_ID,
                            config=PromptLayerConfig(
                                prefix="You are a concise assistant.",
                                user="Say hello from the synchronous DATA Agent client example.",
                            ),
                        ),
                        RunLayerSpec(
                            name="execution_context",
                            type=DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
                            config=DATAExecutionContextLayerConfig(
                                tenant_id=TENANT_ID,
                                user_from="account",
                                agent_mode="workflow_run",
                                invoke_from="service-api",
                            ),
                        ),
                        RunLayerSpec(
                            name=DATA_AGENT_MODEL_LAYER_ID,
                            type=DATA_PLUGIN_LLM_LAYER_TYPE_ID,
                            deps={"execution_context": "execution_context"},
                            config=DATAPluginLLMLayerConfig(
                                plugin_id=PLUGIN_ID,
                                model_provider=PLUGIN_PROVIDER,
                                model=MODEL_NAME,
                                credentials=MODEL_CREDENTIALS,
                            ),
                        ),
                        # Minimal plugin-tools example. API callers should pass
                        # prepared parameters + JSON schema instead of relying on
                        # data-agent to fetch and merge daemon declarations.
                        # from data_agent.layers.data_plugin import (
                        #     DATAPluginToolConfig,
                        #     DATAPluginToolParameter,
                        #     DATAPluginToolParameterForm,
                        #     DATAPluginToolParameterType,
                        #     DATAPluginToolsLayerConfig,
                        # )
                        # RunLayerSpec(
                        #     name="tools",
                        #     type="data.plugin.tools",
                        #     deps={"execution_context": "execution_context"},
                        #     config=DATAPluginToolsLayerConfig(
                        #         tools=[
                        #             DATAPluginToolConfig(
                        #                 plugin_id="langgenius/search",
                        #                 provider="search",
                        #                 tool_name="web_search",
                        #                 credential_type="api-key",
                        #                 credentials={"api_key": "replace-with-tool-key"},
                        #                 runtime_parameters={"site": "docs.data.ai"},
                        #                 parameters=[
                        #                     DATAPluginToolParameter(
                        #                         name="query",
                        #                         type=DATAPluginToolParameterType.STRING,
                        #                         form=DATAPluginToolParameterForm.LLM,
                        #                         required=True,
                        #                         llm_description="Search query",
                        #                     ),
                        #                 ],
                        #                 parameters_json_schema={
                        #                     "type": "object",
                        #                     "properties": {
                        #                         "query": {"type": "string", "description": "Search query"}
                        #                     },
                        #                     "required": ["query"],
                        #                 },
                        #             )
                        #         ]
                        #     ),
                        # ),
                    ],
                ),
            )
        )
        print("created run", run)
        terminal = client.wait_run_sync(run.run_id, poll_interval_seconds=0.5)
        print("terminal status", terminal)


if __name__ == "__main__":
    main()
