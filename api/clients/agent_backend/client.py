"""Synchronous API-side wrapper around the public ``data-agent`` client.

``data-agent`` owns the cross-service DTOs and HTTP/SSE implementation. The API
backend keeps this thin wrapper so workflow code depends on a local protocol,
gets API-native errors, and can use a deterministic fake in tests without
creating another wire contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from data_agent.client import (
    DATAAgentClientError,
    DATAAgentHTTPError,
    DATAAgentStreamError,
    DATAAgentTimeoutError,
    DATAAgentValidationError,
)
from data_agent.protocol import (
    CancelRunRequest,
    CancelRunResponse,
    CreateRunRequest,
    CreateRunResponse,
    RunEvent,
    RunStatusResponse,
)

from clients.agent_backend.errors import (
    AgentBackendError,
    AgentBackendHTTPError,
    AgentBackendStreamError,
    AgentBackendTransportError,
    AgentBackendValidationError,
)


class AgentBackendRunClient(Protocol):
    """Local boundary used by API workflow integrations to run Agent backend jobs."""

    def create_run(self, request: CreateRunRequest) -> CreateRunResponse:
        """Create one Agent backend run and return its accepted status."""

    def cancel_run(self, run_id: str, request: CancelRunRequest | None = None) -> CancelRunResponse:
        """Request explicit cancellation for one Agent backend run."""

    def stream_events(self, run_id: str, *, after: str | None = None) -> Iterator[RunEvent]:
        """Yield public ``data-agent`` run events in stream order."""

    def wait_run(self, run_id: str, *, timeout_seconds: float | None = None) -> RunStatusResponse:
        """Wait for a run to reach a terminal status and return that status."""


class _DATAAgentSyncClient(Protocol):
    """Subset of ``data_agent.client.Client`` used by the API wrapper."""

    def create_run_sync(self, request: CreateRunRequest) -> CreateRunResponse:
        """Create one run synchronously."""

    def cancel_run_sync(self, run_id: str, request: CancelRunRequest | None = None) -> CancelRunResponse:
        """Cancel one run synchronously."""

    def stream_events_sync(self, run_id: str, *, after: str | None = None) -> Iterator[RunEvent]:
        """Stream run events synchronously."""

    def wait_run_sync(self, run_id: str, *, timeout_seconds: float | None = None) -> RunStatusResponse:
        """Wait for terminal run status synchronously."""


class DATAAgentBackendRunClient:
    """Adapter from API sync call sites to ``data_agent.client.Client`` sync methods."""

    client: _DATAAgentSyncClient

    def __init__(self, client: _DATAAgentSyncClient) -> None:
        self.client = client

    def create_run(self, request: CreateRunRequest) -> CreateRunResponse:
        """Create one run through ``POST /runs`` and normalize client exceptions."""
        try:
            return self.client.create_run_sync(request)
        except Exception as exc:
            raise _normalize_data_agent_error(exc) from exc

    def cancel_run(self, run_id: str, request: CancelRunRequest | None = None) -> CancelRunResponse:
        """Cancel one run through ``POST /runs/{run_id}/cancel`` and normalize exceptions."""
        try:
            return self.client.cancel_run_sync(run_id, request=request)
        except Exception as exc:
            raise _normalize_data_agent_error(exc) from exc

    def stream_events(self, run_id: str, *, after: str | None = None) -> Iterator[RunEvent]:
        """Stream run events from ``/events/sse`` with the wrapped client's reconnect policy."""
        try:
            yield from self.client.stream_events_sync(run_id, after=after)
        except Exception as exc:
            raise _normalize_data_agent_error(exc) from exc

    def wait_run(self, run_id: str, *, timeout_seconds: float | None = None) -> RunStatusResponse:
        """Poll run status until terminal state and normalize client exceptions."""
        try:
            return self.client.wait_run_sync(run_id, timeout_seconds=timeout_seconds)
        except Exception as exc:
            raise _normalize_data_agent_error(exc) from exc


def _normalize_data_agent_error(exc: Exception) -> AgentBackendError:
    """Map public ``data-agent`` client errors to API-side integration errors."""
    match exc:
        case DATAAgentValidationError() as error:
            return AgentBackendValidationError(
                "Agent backend request or response validation failed", detail=error.detail
            )
        case DATAAgentHTTPError() as error:
            return AgentBackendHTTPError(
                f"Agent backend HTTP {error.status_code}",
                status_code=error.status_code,
                detail=error.detail,
            )
        case DATAAgentTimeoutError() as error:
            return AgentBackendTransportError(str(error))
        case DATAAgentStreamError() as error:
            return AgentBackendStreamError(str(error))
        case DATAAgentClientError() as error:
            return AgentBackendTransportError(str(error))
        case AgentBackendError() as error:
            return error
        case _:
            return AgentBackendTransportError(str(exc) or type(exc).__name__)
