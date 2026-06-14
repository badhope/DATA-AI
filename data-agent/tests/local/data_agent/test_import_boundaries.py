from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run_import_check(*, blocked_imports: list[str], imports: list[str], assertions: list[str]) -> None:
    python_path = os.pathsep.join([str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH", "")])
    module_aliases = {module_name: module_name.replace(".", "_") for module_name in imports}
    script = "\n".join(
        [
            "import builtins",
            "import importlib",
            f"blocked_imports = {blocked_imports!r}",
            f"imports = {imports!r}",
            f"module_aliases = {module_aliases!r}",
            f"assertions = {assertions!r}",
            "original_import = builtins.__import__",
            "def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):",
            "    for blocked in blocked_imports:",
            "        if name == blocked or name.startswith(f'{blocked}.'):",
            "            raise ModuleNotFoundError(f'blocked import: {name}')",
            "    return original_import(name, globals, locals, fromlist, level)",
            "builtins.__import__ = guarded_import",
            "namespace = {}",
            "for module_name in imports:",
            "    namespace[module_aliases[module_name]] = importlib.import_module(module_name)",
            "for statement in assertions:",
            "    exec(statement, namespace)",
        ]
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = python_path

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_data_agent_root_import_is_client_safe() -> None:
    _run_import_check(
        blocked_imports=[
            "anthropic",
            "data_agent.adapters.llm",
            "data_agent.runtime",
            "data_agent.server",
            "fastapi",
            "google",
            "graphon",
            "openai",
            "pydantic_settings",
            "redis",
        ],
        imports=["data_agent"],
        assertions=[
            "from data_agent import Client",
            "assert data_agent.__all__ == ['Client']",
            "assert data_agent.Client is Client",
            "assert not hasattr(data_agent, 'DATALLMAdapterModel')",
            "assert not hasattr(data_agent, 'DATAPluginDaemonProvider')",
        ],
    )


def test_protocol_and_data_plugin_exports_do_not_import_server_only_modules() -> None:
    _run_import_check(
        blocked_imports=[
            "anthropic",
            "data_agent.adapters.llm",
            "data_agent.layers.drive.layer",
            "data_agent.layers.execution_context.layer",
            "data_agent.layers.ask_human.layer",
            "data_agent.layers.data_plugin.llm_layer",
            "data_agent.layers.data_plugin.tools_layer",
            "data_agent.layers.output.output_layer",
            "data_agent.layers.shell.layer",
            "data_agent.runtime",
            "data_agent.server",
            "fastapi",
            "google",
            "graphon",
            "openai",
            "pydantic_settings",
            "redis",
            "shell_session_manager.shellctl.client",
            "shell_session_manager.shellctl.server",
        ],
        imports=[
            "data_agent.protocol",
            "data_agent.layers.drive",
            "data_agent.layers.execution_context",
            "data_agent.layers.ask_human",
            "data_agent.layers.data_plugin",
            "data_agent.layers.output",
            "data_agent.layers.shell",
        ],
        assertions=[
            "assert hasattr(data_agent_protocol, 'PydanticAIStreamRunEvent')",
            "assert data_agent_layers_drive.__all__ == ['DATA_DRIVE_LAYER_TYPE_ID', 'DATADriveFileConfig', 'DATADriveLayerConfig', 'DATADriveSkillConfig']",
            "assert data_agent_layers_execution_context.__all__ == ['DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID', 'DATAExecutionContextAgentMode', 'DATAExecutionContextInvokeFrom', 'DATAExecutionContextLayerConfig', 'DATAExecutionContextUserFrom']",
            "assert data_agent_layers_ask_human.__all__ == ['AskHumanAction', 'AskHumanActionStyle', 'AskHumanField', 'AskHumanFieldType', 'AskHumanFileField', 'AskHumanFileListField', 'AskHumanParagraphField', 'AskHumanResultStatus', 'AskHumanSelectField', 'AskHumanSelectOption', 'AskHumanSelectedAction', 'AskHumanToolArgs', 'AskHumanToolResult', 'AskHumanUrgency', 'DEFAULT_ASK_HUMAN_TOOL_DESCRIPTION', 'DATA_ASK_HUMAN_LAYER_TYPE_ID', 'DATAAskHumanLayerConfig']",
            "assert data_agent_layers_data_plugin.__all__ == ['DATA_PLUGIN_LLM_LAYER_TYPE_ID', 'DATA_PLUGIN_TOOLS_LAYER_TYPE_ID', 'DATAPluginCredentialValue', 'DATAPluginLLMLayerConfig', 'DATAPluginToolCredentialType', 'DATAPluginToolConfig', 'DATAPluginToolOption', 'DATAPluginToolParameter', 'DATAPluginToolParameterForm', 'DATAPluginToolParameterType', 'DATAPluginToolsLayerConfig', 'DATAPluginToolValue']",
            "assert data_agent_layers_output.__all__ == ['DATA_OUTPUT_LAYER_TYPE_ID', 'DATAOutputLayerConfig']",
            "assert data_agent_layers_shell.__all__ == ['DATA_SHELL_LAYER_TYPE_ID', 'DATAShellCliToolConfig', 'DATAShellEnvVarConfig', 'DATAShellLayerConfig', 'DATAShellSandboxConfig', 'DATAShellSecretRefConfig']",
        ],
    )


def test_agent_stub_cli_main_import_is_client_safe() -> None:
    _run_import_check(
        blocked_imports=[
            "data_agent.server",
            "data_agent.agent_stub.server",
            "fastapi",
            "google.protobuf",
            "grpclib",
            "jwcrypto",
            "pydantic_settings",
            "redis",
            "shell_session_manager",
        ],
        imports=["data_agent.agent_stub.cli.main"],
        assertions=["assert hasattr(data_agent_agent_stub_cli_main, 'main')"],
    )


def test_agent_stub_client_and_protocol_imports_are_client_safe() -> None:
    _run_import_check(
        blocked_imports=[
            "data_agent.server",
            "data_agent.agent_stub.server",
            "fastapi",
            "jwcrypto",
            "pydantic_settings",
            "redis",
            "shell_session_manager",
        ],
        imports=["data_agent.agent_stub.client", "data_agent.agent_stub.protocol"],
        assertions=[
            "assert hasattr(data_agent_agent_stub_client, 'connect_agent_stub_sync')",
            "assert hasattr(data_agent_agent_stub_protocol, 'AgentStubConnectRequest')",
        ],
    )


def test_agenton_collection_roots_do_not_eagerly_import_pydantic_ai_implementations() -> None:
    _run_import_check(
        blocked_imports=[
            "agenton_collections.layers.pydantic_ai",
            "agenton_collections.transformers.pydantic_ai",
        ],
        imports=["agenton_collections", "agenton_collections.transformers"],
        assertions=[
            "assert 'PydanticAIBridgeLayer' not in agenton_collections.__all__",
            "assert agenton_collections_transformers.__all__ == []",
        ],
    )
