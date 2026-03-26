"""Tests for API key authentication middleware."""

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings(monkeypatch):
    """Set up test environment variables."""
    # IMAP settings
    monkeypatch.setenv("IMAP_HOST", "imap.test.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@test.com")
    monkeypatch.setenv("IMAP_PASSWORD", "test123")
    monkeypatch.setenv("IMAP_SSL", "true")

    # SMTP settings
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test123")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    # MCP settings
    monkeypatch.setenv("MCP_API_KEY", "test-secret-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    # Reload config to pick up test env vars
    import importlib
    import config
    importlib.reload(config)


@pytest.fixture
def test_app(mock_settings):
    """Create a test FastAPI app with auth middleware."""
    from auth import verify_api_key

    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(verify_api_key)])
    async def protected_route():
        return {"message": "success"}

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


def test_request_with_correct_api_key_is_allowed(test_app):
    """Test that requests with correct X-API-Key header are allowed."""
    client = TestClient(test_app)

    response = client.get(
        "/protected",
        headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "success"}


def test_request_with_missing_api_key_returns_401(test_app):
    """Test that requests with missing X-API-Key return 401."""
    client = TestClient(test_app)

    response = client.get("/protected")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_request_with_incorrect_api_key_returns_401(test_app):
    """Test that requests with incorrect X-API-Key return 401."""
    client = TestClient(test_app)

    response = client.get(
        "/protected",
        headers={"X-API-Key": "wrong-key"}
    )

    assert response.status_code == 401
    assert "detail" in response.json()


def test_request_with_empty_api_key_returns_401(test_app):
    """Test that requests with empty X-API-Key return 401."""
    client = TestClient(test_app)

    response = client.get(
        "/protected",
        headers={"X-API-Key": ""}
    )

    assert response.status_code == 401


def test_health_check_bypasses_auth(test_app):
    """Test that health check endpoint bypasses auth (no auth dependency)."""
    client = TestClient(test_app)

    # Should work without API key
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_case_sensitive_header_name(test_app):
    """Test that header name matching is case-insensitive (HTTP standard)."""
    client = TestClient(test_app)

    # FastAPI/Starlette normalizes headers to lowercase, so both should work
    response = client.get(
        "/protected",
        headers={"x-api-key": "test-secret-key"}  # lowercase
    )

    assert response.status_code == 200
