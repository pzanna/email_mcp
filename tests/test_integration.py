"""Integration smoke test for all 7 MCP tools."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import json


@pytest.fixture
def mock_settings(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("IMAP_HOST", "imap.test.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@test.com")
    monkeypatch.setenv("IMAP_PASSWORD", "test123")
    monkeypatch.setenv("IMAP_SSL", "true")

    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test123")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-secret-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    import importlib
    import config
    importlib.reload(config)


def test_get_mcp_tools_lists_all_7_tools(mock_settings):
    """Test that GET /mcp/tools returns all 7 tools."""
    from main import app

    client = TestClient(app)

    response = client.get(
        "/mcp/tools",
        headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) == 7

    tool_names = {tool["name"] for tool in data["tools"]}
    expected_tools = {
        "list_folders", "search_emails", "read_email",
        "mark_email", "move_email", "send_email", "reply_email"
    }
    assert tool_names == expected_tools


def test_mcp_tools_endpoint_requires_auth(mock_settings):
    """Test that /mcp/tools requires authentication."""
    from main import app

    client = TestClient(app)

    # Without API key
    response = client.get("/mcp/tools")
    assert response.status_code == 401

    # With wrong API key
    response = client.get(
        "/mcp/tools",
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


def test_health_check_works_without_auth(mock_settings):
    """Test that /health works without authentication."""
    from main import app

    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_mcp_call_all_tools_return_correct_schema(mock_settings):
    """Test that POST /mcp/call works for all 7 tools with mocked backends."""
    from main import app
    from unittest.mock import AsyncMock, MagicMock

    client = TestClient(app)

    # Mock IMAP client — all UID-based operations go through uid_search / uid()
    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=("OK", [b'(\\HasNoChildren) "/" "INBOX"']))
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid_search = AsyncMock(return_value=("OK", [b"123"]))

    # uid() handles FETCH, STORE, COPY, MOVE — route by first positional arg
    _email_headers = (
        b'From: test@test.com\r\n'
        b'To: me@test.com\r\n'
        b'Subject: Test\r\n'
        b'Date: Mon, 10 Mar 2024 09:15:00 +0000\r\n'
        b'Message-ID: <orig@test.com>\r\n'
        b'\r\n'
        b'Body'
    )
    _fetch_response = (
        "OK",
        [
            b'123 (FLAGS (\\Seen) RFC822 {200}',
            bytearray(_email_headers),
            b')',
            b'A001 OK FETCH completed',
        ]
    )

    async def _uid_router(cmd, *args, **kwargs):
        if cmd in ("FETCH",):
            return _fetch_response
        return ("OK", [b"OK"])

    mock_client.uid = AsyncMock(side_effect=_uid_router)
    mock_client.expunge = AsyncMock(return_value=("OK", []))
    mock_client.logout = AsyncMock(return_value=("OK", []))
    mock_client.close = AsyncMock()

    # Create a mock context manager for the pool
    mock_pool_ctx = MagicMock()
    mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_pool_ctx.__aexit__ = AsyncMock(return_value=None)

    # Patch in all modules that use imap_pool
    patches = [
        patch("imap.read.imap_pool"),
        patch("imap.search.imap_pool"),
        patch("imap.flags.imap_pool"),
    ]

    # Apply all patches
    mock_pools = []
    for p in patches:
        mock_pool = p.start()
        mock_pool.acquire_connection.return_value = mock_pool_ctx
        mock_pools.append(mock_pool)

    try:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_smtp:
            # Set up SMTP mock
            mock_smtp.return_value = "<msg@test.com>"

            # Test list_folders
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "list_folders",
                        "arguments": {}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "content" in data
            assert len(data["content"]) > 0
            result = json.loads(data["content"][0]["text"])
            assert "folders" in result

            # Test search_emails
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "search_emails",
                        "arguments": {"limit": 10}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

            # Test read_email
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "read_email",
                        "arguments": {"uid": "123"}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

            # Test mark_email
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "mark_email",
                        "arguments": {"uid": "123", "read": True}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

            # Test move_email
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "move_email",
                        "arguments": {"uid": "123", "to_folder": "Archive"}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

            # Test send_email
            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "send_email",
                        "arguments": {
                            "to": ["user@test.com"],
                            "subject": "Test",
                            "body": "Body"
                        }
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

            # Test reply_email — uid() already returns the right flat response

            response = client.post(
                "/mcp/call",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "reply_email",
                        "arguments": {"uid": "123", "body": "Reply"}
                    }
                },
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

    finally:
        # Clean up patches
        for p in patches:
            p.stop()
