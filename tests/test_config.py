"""Tests for configuration loading and validation."""

import pytest
from pydantic import ValidationError


def test_config_loads_all_required_env_vars(monkeypatch):
    """Test that all required environment variables are loaded correctly."""
    # Set all required env vars
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    # Reload config module to pick up new env vars
    import importlib
    import config
    importlib.reload(config)

    from config import settings

    # Verify IMAP settings
    assert settings.IMAP_HOST == "imap.example.com"
    assert settings.IMAP_PORT == 993
    assert settings.IMAP_USER == "test@example.com"
    assert settings.IMAP_PASSWORD == "secret123"
    assert settings.IMAP_SSL is True

    # Verify SMTP settings
    assert settings.SMTP_HOST == "smtp.example.com"
    assert settings.SMTP_PORT == 587
    assert settings.SMTP_USER == "test@example.com"
    assert settings.SMTP_PASSWORD == "secret456"
    assert settings.SMTP_STARTTLS == "true"

    # Verify MCP settings
    assert settings.MCP_API_KEY == "test-api-key"
    assert settings.MCP_HOST == "127.0.0.1"
    assert settings.MCP_PORT == 8420


def test_config_applies_default_values(monkeypatch):
    """Test that default values are applied for optional fields."""
    # Set only required env vars
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    # Reload config
    import importlib
    import config
    importlib.reload(config)

    from config import settings

    # Verify defaults
    assert settings.IMAP_POOL_SIZE == 3
    assert settings.MAX_SEARCH_RESULTS == 50
    assert settings.MCP_SERVER_NAME == "email-mcp"
    assert settings.MCP_BASE_URL == "http://localhost:8420"


def test_config_missing_required_vars_raises_error(monkeypatch):
    """Test that missing required environment variables raise validation errors."""
    # Clear all env vars
    for key in ["IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "IMAP_SSL",
                "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS",
                "MCP_API_KEY", "MCP_HOST", "MCP_PORT"]:
        monkeypatch.delenv(key, raising=False)

    # Attempting to import config should raise ValidationError
    with pytest.raises(ValidationError):
        import importlib
        import config
        importlib.reload(config)


def test_config_invalid_port_raises_error(monkeypatch):
    """Test that non-numeric port values raise validation errors."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "not-a-number")  # Invalid
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    with pytest.raises(ValidationError):
        import importlib
        import config
        importlib.reload(config)


def test_config_invalid_boolean_raises_error(monkeypatch):
    """Test that invalid boolean values raise validation errors."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "not-a-bool")  # Invalid

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    with pytest.raises(ValidationError):
        import importlib
        import config
        importlib.reload(config)


def test_config_smtp_starttls_normalizes_case_and_whitespace(monkeypatch):
    """Test that SMTP_STARTTLS is normalized to lowercase accepted values."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", " NONE ")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    import importlib
    import config
    importlib.reload(config)

    from config import settings

    assert settings.SMTP_STARTTLS == "none"


def test_config_invalid_smtp_starttls_raises_error(monkeypatch):
    """Test that SMTP_STARTTLS rejects unsupported string values."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "maybe")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    with pytest.raises(ValidationError):
        import importlib
        import config
        importlib.reload(config)


def test_config_is_singleton(monkeypatch):
    """Test that config is accessible as a singleton via 'from config import settings'."""
    # Set required env vars
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret456")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    # Reload config
    import importlib
    import config
    importlib.reload(config)

    # Import settings twice
    from config import settings as settings1
    from config import settings as settings2

    # They should be the same object
    assert settings1 is settings2
