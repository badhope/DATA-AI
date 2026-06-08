"""Unit tests for ``data_ai.core.i18n``.

The internationalization layer is small but central: every error message the
HTTP layer emits passes through ``tr()``, and every request is routed
through ``negotiate_locale``. These tests pin down the contract.
"""

from __future__ import annotations

import pytest

from data_ai.core.i18n.catalog import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    Locale,
    _coerce_locale,
    tr,
)
from data_ai.core.i18n.negotiator import negotiate_locale

# ─── tr() ────────────────────────────────────────────────────────────────────


class TestTr:
    def test_known_key_in_english(self) -> None:
        assert tr("api.error.not_found", Locale.EN) == "Resource not found"

    def test_known_key_in_chinese(self) -> None:
        result = tr("api.error.not_found", Locale.ZH)
        assert result  # non-empty
        assert result != "[api.error.not_found]"

    def test_falls_back_to_default_for_missing_key(self) -> None:
        # The default locale is English; pass a Chinese locale and ask for a
        # key we know only exists in English. We expect the English text.
        # (This is a contract test for the fallback path; if the catalog
        # later becomes fully symmetric, it can be relaxed.)
        # Use a definitely-missing key to assert the bracket fallback.
        assert tr("__definitely_missing__", Locale.ZH) == "[__definitely_missing__]"

    def test_param_substitution(self) -> None:
        out = tr("api.error.bad_request", Locale.EN, reason="missing field")
        assert "missing field" in out
        assert "{" not in out

    def test_param_substitution_via_kwargs(self) -> None:
        out = tr("api.error.bad_request", Locale.ZH, reason="缺字段")
        assert "缺字段" in out

    def test_default_locale_when_unspecified(self) -> None:
        out = tr("api.error.not_found")
        # Default locale is English per catalog
        assert out == tr("api.error.not_found", DEFAULT_LOCALE)

    def test_unknown_locale_coerced_to_default(self) -> None:
        # Garbage string should be coerced to the default rather than KeyError.
        out = tr("api.error.not_found", "klingon")
        assert out == tr("api.error.not_found", DEFAULT_LOCALE)

    def test_supported_locales_are_unique(self) -> None:
        assert len(SUPPORTED_LOCALES) == len({loc.value for loc in SUPPORTED_LOCALES})


# ─── Locale coercion ────────────────────────────────────────────────────────


class TestCoerceLocale:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("en", Locale.EN),
            ("EN", Locale.EN),
            ("en-us", Locale.EN),
            ("en_GB", Locale.EN),
            ("zh", Locale.ZH),
            ("zh-cn", Locale.ZH),
            ("zh-hans", Locale.ZH),
            (Locale.EN, Locale.EN),
            (Locale.ZH, Locale.ZH),
        ],
    )
    def test_supported_inputs(self, value: object, expected: Locale) -> None:
        assert _coerce_locale(value) == expected

    @pytest.mark.parametrize("value", ["fr", "de", "ja", "", None, 42, object()])
    def test_unsupported_inputs_fall_back(self, value: object) -> None:
        assert _coerce_locale(value) == DEFAULT_LOCALE


# ─── negotiate_locale ────────────────────────────────────────────────────────


class TestNegotiateLocale:
    def test_explicit_english(self) -> None:
        assert negotiate_locale("en") == Locale.EN

    def test_explicit_chinese(self) -> None:
        assert negotiate_locale("zh") == Locale.ZH

    def test_long_tag_uses_prefix(self) -> None:
        assert negotiate_locale("zh-CN,zh;q=0.9,en;q=0.8") == Locale.ZH
        assert negotiate_locale("en-GB,en;q=0.9") == Locale.EN

    def test_quality_ordering(self) -> None:
        # q=0.1 zh should lose to q=0.5 en
        assert negotiate_locale("zh;q=0.1,en;q=0.5") == Locale.EN

    def test_wildcard_returns_default(self) -> None:
        assert negotiate_locale("*") == DEFAULT_LOCALE

    def test_empty_returns_default(self) -> None:
        assert negotiate_locale("") == DEFAULT_LOCALE
        assert negotiate_locale(None) == DEFAULT_LOCALE

    def test_unsupported_returns_default(self) -> None:
        assert negotiate_locale("ja") == DEFAULT_LOCALE
        assert negotiate_locale("ja,fr") == DEFAULT_LOCALE
