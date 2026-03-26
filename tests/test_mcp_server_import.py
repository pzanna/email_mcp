"""Smoke test: mcp_server.py can be imported without crashing when env vars are set."""
import os
import pytest

# Minimal valid env vars for Settings()
FAKE_ENV = {
    "IMAP_HOST": "imap.test.local",
    "IMAP_PORT": "993",
    "IMAP_USER": "user@test.local",
    "IMAP_PASSWORD": "secret",
    "IMAP_SSL": "true",
    "SMTP_HOST": "smtp.test.local",
    "SMTP_PORT": "587",
    "SMTP_USER": "user@test.local",
    "SMTP_PASSWORD": "secret",
    "SMTP_STARTTLS": "true",
    "MCP_API_KEY": "testkey",
}


def test_mcp_server_importable(monkeypatch):
    """mcp_server module can be imported when env vars are present."""
    for k, v in FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    # Must NOT raise
    import importlib
    import sys
    # Remove cached modules so fresh import picks up monkeypatched env
    for mod in list(sys.modules.keys()):
        if mod in ("config", "imap.client", "mcp_server"):
            del sys.modules[mod]

    import mcp_server  # noqa: F401
    assert hasattr(mcp_server, "server")
    assert hasattr(mcp_server, "main")
