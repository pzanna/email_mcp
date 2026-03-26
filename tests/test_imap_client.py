"""Tests for IMAP client and connection pool."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aioimaplib import IMAP4_SSL


@pytest.fixture
def mock_settings(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("IMAP_HOST", "imap.test.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "test@test.com")
    monkeypatch.setenv("IMAP_PASSWORD", "test123")
    monkeypatch.setenv("IMAP_SSL", "true")
    monkeypatch.setenv("IMAP_POOL_SIZE", "3")

    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test123")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    monkeypatch.setenv("MCP_API_KEY", "test-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    # Reload config
    import importlib
    import config
    importlib.reload(config)


@pytest.mark.asyncio
async def test_connection_pool_initializes_with_correct_size(mock_settings):
    """Test that connection pool initializes with correct size."""
    from imap.client import IMAPPool

    pool = IMAPPool(pool_size=3)
    assert pool._semaphore._value == 3


@pytest.mark.asyncio
async def test_acquire_connection_returns_connected_client(mock_settings):
    """Test that acquire_connection returns a connected IMAP client."""
    from imap.client import IMAPPool

    # Mock IMAP4_SSL
    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client):
        async with pool.acquire_connection() as client:
            assert client is not None
            # Verify connection was established
            mock_client.wait_hello_from_server.assert_called_once()
            mock_client.login.assert_called_once()


@pytest.mark.asyncio
async def test_release_connection_returns_client_to_pool(mock_settings):
    """Test that release_connection calls logout; close() only when SELECTED."""
    from imap.client import IMAPPool

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client):
        async with pool.acquire_connection() as client:
            pass  # Exit context — no SELECT issued, state is not SELECTED

        # logout must always be called
        mock_client.logout.assert_called_once()
        # close must NOT be called: after logout the state is LOGOUT, not SELECTED
        mock_client.close.assert_not_called()


@pytest.mark.asyncio
async def test_release_connection_calls_close_when_selected(mock_settings):
    """Test that release_connection calls close() when a mailbox is selected."""
    from imap.client import IMAPPool

    mock_protocol = MagicMock()
    mock_protocol.state = "SELECTED"

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.protocol = mock_protocol

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client):
        async with pool.acquire_connection() as client:
            pass  # Exit with protocol.state == SELECTED

        mock_client.logout.assert_called_once()
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_pool_handles_concurrent_requests(mock_settings):
    """Test that pool limits concurrent connections to pool_size."""
    from imap.client import IMAPPool

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()

    pool = IMAPPool(pool_size=3)
    connection_count = 0
    max_concurrent = 0

    async def acquire_and_hold():
        nonlocal connection_count, max_concurrent
        with patch("imap.client.IMAP4_SSL", return_value=mock_client):
            async with pool.acquire_connection():
                connection_count += 1
                max_concurrent = max(max_concurrent, connection_count)
                await asyncio.sleep(0.01)  # Hold connection briefly
                connection_count -= 1

    # Spawn 5 tasks but pool size is 3
    tasks = [acquire_and_hold() for _ in range(5)]
    await asyncio.gather(*tasks)

    # Max concurrent connections should never exceed pool size
    assert max_concurrent <= 3


@pytest.mark.asyncio
async def test_connection_failure_raises_appropriate_error(mock_settings):
    """Test that connection failures raise appropriate errors."""
    from imap.client import IMAPPool

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock(side_effect=Exception("Connection refused"))

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client):
        with pytest.raises(Exception, match="Connection refused"):
            async with pool.acquire_connection():
                pass


@pytest.mark.asyncio
async def test_ssl_connection_when_imap_ssl_true(mock_settings):
    """Test that SSL connection is used when IMAP_SSL is true."""
    from imap.client import IMAPPool

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client) as mock_ssl_class:
        async with pool.acquire_connection():
            # Verify IMAP4_SSL was called (not IMAP4)
            mock_ssl_class.assert_called_once()


@pytest.mark.asyncio
async def test_auth_failure_raises_imap_auth_failed(mock_settings):
    """Test that authentication failures raise IMAP_AUTH_FAILED error."""
    from imap.client import IMAPPool

    mock_client = AsyncMock(spec=IMAP4_SSL)
    mock_client.wait_hello_from_server = AsyncMock()
    mock_client.login = AsyncMock(return_value=("NO", [b"Authentication failed"]))
    mock_client.logout = AsyncMock()
    mock_client.close = AsyncMock()

    pool = IMAPPool(pool_size=1)

    with patch("imap.client.IMAP4_SSL", return_value=mock_client):
        with pytest.raises(Exception, match="IMAP_AUTH_FAILED|Authentication failed"):
            async with pool.acquire_connection():
                pass
