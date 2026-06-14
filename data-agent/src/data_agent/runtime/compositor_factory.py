"""Safe Agenton compositor construction for API-submitted configs.

Only explicitly allowed provider type ids are constructible here. The default
provider set contains prompt layers, the optional pydantic-ai history layer, the
state-free DATA structured output layer, the optional DATA ask-human layer, the
DATA execution-context layer, the stateful DATA shell layer, and the DATA
plugin business-layer family:

- ``data.drive`` for the inert Skills & Files drive declaration,
- ``data.execution_context`` for shared tenant/user/run daemon context,
- ``data.shell`` for shellctl-backed shell job control,
- ``data.plugin.llm`` for plugin-backed model selection, and
- ``data.plugin.tools`` for prepared plugin tool exposure.

Public DTOs provide DATA context plus plugin/model/tool data, while server-only
plugin daemon settings are injected through the provider factory for
``DATAExecutionContextLayer`` and the optional shellctl entrypoint/auth token plus
client factory plus optional Agent Stub URL/token issuer are injected for
``DATAShellLayer``. The resulting ``Compositor``
remains Agenton state-only at the snapshot boundary: live resources such as
HTTP clients are injected by runtime-owned providers, may be held on active
layer instances inside ``resource_context()``, and never enter session
snapshots.
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic_ai.messages import UserContent

from agenton.compositor import Compositor, CompositorConfig, LayerProvider, LayerProviderInput
from agenton.layers.types import AllPromptTypes, AllToolTypes, AllUserPromptTypes, PydanticAIPrompt, PydanticAITool
from agenton_collections.layers.pydantic_ai import PydanticAIHistoryLayer
from agenton_collections.layers.plain.basic import PromptLayer
from agenton_collections.transformers.pydantic_ai import PYDANTIC_AI_TRANSFORMERS
from data_agent.agent_stub.server.shell_agent_stub_env import ShellAgentStubTokenFactory
from data_agent.agent_stub.server.tokens.agent_stub import AgentStubTokenCodec
from data_agent.layers.ask_human.layer import DATAAskHumanLayer
from data_agent.layers.data_plugin.llm_layer import DATAPluginLLMLayer
from data_agent.layers.data_plugin.tools_layer import DATAPluginToolsLayer
from data_agent.layers.drive.layer import DATADriveLayer
from data_agent.layers.execution_context.configs import DATAExecutionContextLayerConfig
from data_agent.layers.execution_context.layer import DATAExecutionContextLayer
from data_agent.layers.output.output_layer import DATAOutputLayer
from data_agent.layers.shell.configs import DATAShellLayerConfig
from data_agent.layers.shell.layer import DATAShellLayer, create_shellctl_client_factory

type DATAAgentLayerProvider = LayerProvider[Any]


def create_default_layer_providers(
    *,
    plugin_daemon_url: str = "http://localhost:5002",
    plugin_daemon_api_key: str = "",
    shellctl_entrypoint: str | None = None,
    shellctl_auth_token: str | None = None,
    agent_stub_url: str | None = None,
    agent_stub_token_codec: AgentStubTokenCodec | None = None,
) -> tuple[DATAAgentLayerProvider, ...]:
    """Return the server provider set of safe config-constructible layers.

    ``shellctl_auth_token`` defaults to no token. Passing an explicit empty string
    to ``create_shellctl_client_factory`` prevents ``ShellctlClient`` from falling
    back to the DATA Agent process's ``SHELLCTL_AUTH_TOKEN`` environment variable;
    deployments that enable shellctl bearer auth must set the DATA Agent server
    setting explicitly.
    """
    shellctl_token = shellctl_auth_token or ""
    agent_stub_token_factory: ShellAgentStubTokenFactory | None = None
    if agent_stub_token_codec is not None:

        def build_agent_stub_token(
            execution_context: DATAExecutionContextLayerConfig,
            *,
            session_id: str | None,
        ) -> str:
            return agent_stub_token_codec.encode_connection_token(
                execution_context,
                session_id=session_id,
            )

        agent_stub_token_factory = build_agent_stub_token
    return (
        LayerProvider.from_layer_type(PromptLayer),
        LayerProvider.from_layer_type(PydanticAIHistoryLayer),
        LayerProvider.from_layer_type(DATAOutputLayer),
        LayerProvider.from_layer_type(DATAAskHumanLayer),
        # Inert declaration layer: makes ``data.drive`` a known type id so runs
        # carrying the Skills & Files manifest never fail before the consumption
        # work (ENG-387) lands. Deliberately contributes no prompt and no tools.
        LayerProvider.from_layer_type(DATADriveLayer),
        LayerProvider.from_factory(
            layer_type=DATAExecutionContextLayer,
            create=lambda config: DATAExecutionContextLayer.from_config_with_settings(
                DATAExecutionContextLayerConfig.model_validate(config),
                daemon_url=plugin_daemon_url,
                daemon_api_key=plugin_daemon_api_key,
            ),
        ),
        LayerProvider.from_factory(
            layer_type=DATAShellLayer,
            create=lambda config: DATAShellLayer.from_config_with_settings(
                DATAShellLayerConfig.model_validate(config),
                shellctl_entrypoint=shellctl_entrypoint,
                shellctl_client_factory=create_shellctl_client_factory(token=shellctl_token),
                agent_stub_url=agent_stub_url,
                agent_stub_token_factory=agent_stub_token_factory,
            ),
        ),
        LayerProvider.from_layer_type(DATAPluginLLMLayer),
        LayerProvider.from_layer_type(DATAPluginToolsLayer),
    )


def build_pydantic_ai_compositor(
    config: CompositorConfig,
    *,
    providers: Sequence[LayerProviderInput],
    node_providers: Mapping[str, LayerProviderInput] | None = None,
) -> Compositor[
    PydanticAIPrompt[object],
    PydanticAITool[object],
    AllPromptTypes,
    AllToolTypes,
    UserContent,
    AllUserPromptTypes,
]:
    """Build a Pydantic AI-ready compositor from a validated graph config.

    Prompt, user prompt, and tool conversion is delegated to Agenton's shared
    pydantic-ai transformer preset so DATA Agent does not duplicate conversion
    logic for plain and pydantic-ai layer families. Callers must pass the already
    selected provider set explicitly so provider defaulting stays at outer runtime
    boundaries rather than being duplicated here.
    """
    return cast(
        Compositor[
            PydanticAIPrompt[object],
            PydanticAITool[object],
            AllPromptTypes,
            AllToolTypes,
            UserContent,
            AllUserPromptTypes,
        ],
        Compositor.from_config(
            config,
            providers=providers,
            node_providers=node_providers,
            **PYDANTIC_AI_TRANSFORMERS,  # pyright: ignore[reportArgumentType]
        ),
    )


__all__ = ["DATAAgentLayerProvider", "build_pydantic_ai_compositor", "create_default_layer_providers"]
