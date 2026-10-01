import pytest

from backend.supabase_db import _database_config


def test_secret_key_is_preferred_and_values_are_normalized(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", ' "https://example.supabase.co/" ')
    monkeypatch.setenv("SUPABASE_SECRET_KEY", " secret-value ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-value")

    assert _database_config() == (
        "https://example.supabase.co",
        "secret-value",
    )


def test_legacy_service_role_key_is_supported(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-value")

    assert _database_config() == (
        "https://example.supabase.co",
        "legacy-value",
    )


def test_invalid_url_fails_with_actionable_message(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "not-a-url")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-value")

    with pytest.raises(RuntimeError, match="valid HTTPS URL"):
        _database_config()


def test_missing_database_configuration_is_explicit(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Supabase configuration is missing"):
        _database_config()
