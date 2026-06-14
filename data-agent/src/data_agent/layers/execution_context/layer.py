"""Runtime DATA execution-context layer.

The public config carries DATA-owned execution identifiers plus the tenant/user
daemon context needed by plugin-backed business layers. Server-only daemon URL
and API key are injected by the provider factory. The layer is intentionally
config/settings-only under Agenton's state-only core: it does not open, cache,
close, or snapshot HTTP clients, and its lifecycle hooks remain the inherited
no-op hooks. Runtime code passes the FastAPI lifespan-owned shared
``httpx.AsyncClient`` into ``create_daemon_provider`` or ``create_tool_client``
for each invocation.
"""

from dataclasses import dataclass
from typing import ClassVar

import httpx
from typing_extensions import Self, override

from agenton.layers import EmptyRuntimeState, NoLayerDeps, PlainLayer
from data_agent.adapters.llm import DATAPluginDaemonProvider
from data_agent.layers.data_plugin.tool_client import DATAPluginDaemonToolClient
from data_agent.layers.execution_context.configs import (
    DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
    DATAExecutionContextLayerConfig,
)


@dataclass(slots=True)
class DATAExecutionContextLayer(PlainLayer[NoLayerDeps, DATAExecutionContextLayerConfig, EmptyRuntimeState]):
    """Layer that carries DATA execution context without owning live resources."""

    type_id: ClassVar[str] = DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID

    config: DATAExecutionContextLayerConfig
    daemon_url: str
    daemon_api_key: str

    @classmethod
    @override
    def from_config(cls, config: DATAExecutionContextLayerConfig) -> Self:
        """Reject construction without server-injected daemon settings."""
        del config
        raise TypeError(
            "DATAExecutionContextLayer requires server-side daemon settings and must use a provider factory."
        )

    @classmethod
    def from_config_with_settings(
        cls,
        config: DATAExecutionContextLayerConfig,
        *,
        daemon_url: str,
        daemon_api_key: str,
    ) -> Self:
        """Create the layer from public config plus server-only daemon settings."""
        return cls(config=config, daemon_url=daemon_url, daemon_api_key=daemon_api_key)

    def create_daemon_provider(self, *, plugin_id: str, http_client: httpx.AsyncClient) -> DATAPluginDaemonProvider:
        """Return a daemon provider backed by the shared plugin daemon client.

        Raises:
            RuntimeError: if ``http_client`` has already been closed.
        """
        if http_client.is_closed:
            raise RuntimeError(
                "DATAExecutionContextLayer.create_daemon_provider() requires an open shared HTTP client."
            )
        return DATAPluginDaemonProvider(
            tenant_id=self.config.tenant_id,
            plugin_id=plugin_id,
            plugin_daemon_url=self.daemon_url,
            plugin_daemon_api_key=self.daemon_api_key,
            user_id=self.config.user_id,
            http_client=http_client,
        )

    def create_tool_client(self, *, plugin_id: str, http_client: httpx.AsyncClient) -> DATAPluginDaemonToolClient:
        """Return a plugin-daemon tool client backed by the shared HTTP client.

        Raises:
            RuntimeError: if ``http_client`` has already been closed.
        """
        if http_client.is_closed:
            raise RuntimeError("DATAExecutionContextLayer.create_tool_client() requires an open shared HTTP client.")
        return DATAPluginDaemonToolClient(
            tenant_id=self.config.tenant_id,
            plugin_id=plugin_id,
            plugin_daemon_url=self.daemon_url,
            plugin_daemon_api_key=self.daemon_api_key,
            user_id=self.config.user_id,
            http_client=http_client,
        )


__all__ = ["DATAExecutionContextLayer"]
