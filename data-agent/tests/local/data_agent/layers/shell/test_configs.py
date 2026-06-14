import pytest
from pydantic import ValidationError

import data_agent.layers.shell as shell_exports
from data_agent.layers.shell import (
    DATA_SHELL_LAYER_TYPE_ID,
    DATAShellCliToolConfig,
    DATAShellEnvVarConfig,
    DATAShellLayerConfig,
    DATAShellSandboxConfig,
    DATAShellSecretRefConfig,
)


def test_shell_package_exports_client_safe_config_symbols_only() -> None:
    assert shell_exports.__all__ == [
        "DATA_SHELL_LAYER_TYPE_ID",
        "DATAShellCliToolConfig",
        "DATAShellEnvVarConfig",
        "DATAShellLayerConfig",
        "DATAShellSandboxConfig",
        "DATAShellSecretRefConfig",
    ]
    assert DATA_SHELL_LAYER_TYPE_ID == "data.shell"
    assert not hasattr(shell_exports, "DATAShellLayer")


def test_shell_layer_config_defaults_and_forbids_unknown_fields() -> None:
    config = DATAShellLayerConfig()

    assert config.model_dump() == {
        "cli_tools": [],
        "env": [],
        "secret_refs": [],
        "sandbox": None,
    }

    with pytest.raises(ValidationError):
        _ = DATAShellLayerConfig.model_validate({"entrypoint": "http://shellctl"})


def test_shell_layer_config_accepts_agent_soul_shell_settings() -> None:
    config = DATAShellLayerConfig(
        cli_tools=[
            DATAShellCliToolConfig(
                name="ripgrep",
                install_commands=["  apt-get update  ", "", "apt-get install -y ripgrep"],
                env=[DATAShellEnvVarConfig(name="RG_CONFIG_PATH", value="/workspace/.ripgreprc")],
                secret_refs=[DATAShellSecretRefConfig(name="GITHUB_TOKEN", ref="credential-2")],
            )
        ],
        env=[DATAShellEnvVarConfig(name="PROJECT_NAME", value="demo")],
        secret_refs=[DATAShellSecretRefConfig(name="OPENAI_API_KEY", ref="credential-1")],
        sandbox=DATAShellSandboxConfig(provider="independent", config={"cpu": 2}),
    )

    assert config.cli_tools[0].install_commands == ["apt-get update", "apt-get install -y ripgrep"]
    assert config.cli_tools[0].env[0].name == "RG_CONFIG_PATH"
    assert config.cli_tools[0].secret_refs[0].ref == "credential-2"
    assert config.env[0].name == "PROJECT_NAME"
    assert config.secret_refs[0].ref == "credential-1"
    assert config.sandbox is not None
    assert config.sandbox.config == {"cpu": 2}


def test_shell_layer_config_rejects_invalid_env_names() -> None:
    with pytest.raises(ValidationError):
        _ = DATAShellEnvVarConfig(name="1_BAD", value="x")

    with pytest.raises(ValidationError):
        _ = DATAShellSecretRefConfig(name="BAD-NAME", ref="secret")
