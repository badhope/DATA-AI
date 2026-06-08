"""Unit tests for ``data_ai.core.api.auth``.

The tests cover the FastAPI dependency ``verify_api_key`` in three modes:

* No key configured and ``DATA_AI_DEV_MODE`` unset → every request is rejected
  with 401 (default-deny posture).
* ``DATA_AI_API_KEYS`` is set → only listed bearer keys are accepted.
* ``DATA_AI_DEV_MODE=true`` is set → every request is allowed.

Each case exercises both the ``Authorization: Bearer ...`` and the
``X-Api-Key: ...`` style header.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest


def _reload_auth() -> Any:
    """Reload the auth module so its module-level env reads run again."""
    import data_ai.core.api.auth as auth_mod

    return importlib.reload(auth_mod)


def _run_dependency(coro: Any) -> Any:
    """Drive an ``async`` FastAPI dependency to its result (or raise)."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        # pytest-asyncio case — defer to it.
        return coro
    return loop.run_until_complete(coro)


class TestDefaultDeny:
    """With no key configured, every request must 401."""

    def test_rejects_bearer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import HTTPException

        monkeypatch.delenv("DATA_AI_API_KEYS", raising=False)
        monkeypatch.delenv("DATA_AI_DEV_MODE", raising=False)
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization="Bearer wrong",
                x_api_key=None,
            )

        with pytest.raises(HTTPException) as exc:
            _run_dependency(call())
        assert exc.value.status_code == 401

    def test_rejects_x_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import HTTPException

        monkeypatch.delenv("DATA_AI_API_KEYS", raising=False)
        monkeypatch.delenv("DATA_AI_DEV_MODE", raising=False)
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization=None,
                x_api_key="anything",
            )

        with pytest.raises(HTTPException) as exc:
            _run_dependency(call())
        assert exc.value.status_code == 401

    def test_rejects_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import HTTPException

        monkeypatch.delenv("DATA_AI_API_KEYS", raising=False)
        monkeypatch.delenv("DATA_AI_DEV_MODE", raising=False)
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(authorization=None, x_api_key=None)

        with pytest.raises(HTTPException) as exc:
            _run_dependency(call())
        assert exc.value.status_code == 401


class TestWhitelist:
    """``DATA_AI_API_KEYS`` accepts only the listed keys."""

    def test_accepts_listed_bearer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_AI_API_KEYS", "alpha,beta")
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization="Bearer alpha",
                x_api_key=None,
            )

        assert _run_dependency(call()) == "alpha"

    def test_rejects_unlisted_bearer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import HTTPException

        monkeypatch.setenv("DATA_AI_API_KEYS", "alpha,beta")
        monkeypatch.delenv("DATA_AI_DEV_MODE", raising=False)
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization="Bearer gamma",
                x_api_key=None,
            )

        with pytest.raises(HTTPException) as exc:
            _run_dependency(call())
        assert exc.value.status_code == 401

    def test_accepts_x_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_AI_API_KEYS", "alpha")
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization=None,
                x_api_key="alpha",
            )

        assert _run_dependency(call()) == "alpha"

    def test_whitespace_in_keys_is_tolerated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_AI_API_KEYS", " alpha , beta ")
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(
                authorization="Bearer alpha",
                x_api_key=None,
            )

        assert _run_dependency(call()) == "alpha"


class TestDevMode:
    """``DATA_AI_DEV_MODE=true`` allows everything."""

    @pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE"])
    def test_truthy_values_open_the_door(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("DATA_AI_DEV_MODE", value)
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(authorization=None, x_api_key=None)

        assert _run_dependency(call()) == "dev-mode"

    def test_falsy_value_does_not_open_the_door(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import HTTPException

        monkeypatch.setenv("DATA_AI_DEV_MODE", "false")
        auth_mod = _reload_auth()

        async def call() -> Any:
            return await auth_mod.verify_api_key(authorization=None, x_api_key=None)

        with pytest.raises(HTTPException):
            _run_dependency(call())


class TestClientAuthHelpers:
    """The client-side ``AuthProvider`` subclasses must still work."""

    def test_api_key_as_header(self) -> None:
        from data_ai.core.api.auth import APIKeyAuth

        auth = APIKeyAuth("k", header_name="X-API-Key")
        assert auth.get_headers() == {"X-API-Key": "k"}
        assert auth.get_params() == {}

    def test_api_key_as_bearer(self) -> None:
        from data_ai.core.api.auth import APIKeyAuth

        auth = APIKeyAuth("k", as_bearer=True)
        assert auth.get_headers() == {"Authorization": "Bearer k"}

    def test_api_key_as_query(self) -> None:
        from data_ai.core.api.auth import APIKeyAuth

        auth = APIKeyAuth("k", in_query=True, param_name="api_key")
        assert auth.get_headers() == {}
        assert auth.get_params() == {"api_key": "k"}

    def test_bearer_token(self) -> None:
        from data_ai.core.api.auth import BearerTokenAuth

        auth = BearerTokenAuth("t")
        assert auth.get_headers() == {"Authorization": "Bearer t"}
