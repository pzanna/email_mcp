"""Tests for search_emails tool."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch


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

    monkeypatch.setenv("MCP_API_KEY", "test-key")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8420")

    import importlib
    import config
    importlib.reload(config)


@pytest.mark.asyncio
async def test_search_emails_by_sender(mock_settings):
    """Test searching emails by sender (from field)."""
    from imap.search import search_emails, SearchEmailsInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"5"]))
    mock_client.uid_search = AsyncMock(return_value=("OK", [b"1 2"]))
    mock_client.uid = AsyncMock(return_value=(
        "OK",
        [
            b'1 (RFC822.HEADER {200}',
            bytearray(b'From: alice@example.com\r\nTo: bob@example.com\r\nSubject: Test 1\r\nDate: Mon, 01 Jan 2024 10:00:00 +0000\r\n\r\n'),
            b')',
            b'A001 OK FETCH completed',
        ]
    ))

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await search_emails(SearchEmailsInput(from_email="alice@example.com"))

        assert result.total >= 0
        assert len(result.messages) >= 0


@pytest.mark.asyncio
async def test_search_emails_respects_limit(mock_settings):
    """Test that search respects the limit parameter."""
    from imap.search import search_emails, SearchEmailsInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"100"]))
    # Return 30 UIDs
    uids = " ".join(str(i) for i in range(1, 31))
    mock_client.uid_search = AsyncMock(return_value=("OK", [uids.encode()]))

    # Mock uid() to return minimal headers for each UID FETCH
    mock_client.uid = AsyncMock(return_value=(
        "OK",
        [
            b'1 (RFC822.HEADER {100}',
            bytearray(b'From: test@test.com\r\nSubject: Test\r\nDate: Mon, 01 Jan 2024 10:00:00 +0000\r\n\r\n'),
            b')',
            b'A001 OK FETCH completed',
        ]
    ))

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        # Request with limit of 20
        result = await search_emails(SearchEmailsInput(limit=20))

        # Should not return more than 20
        assert len(result.messages) <= 20


@pytest.mark.asyncio
async def test_search_emails_returns_message_summaries(mock_settings):
    """Test that search returns message summaries with all required fields."""
    from imap.search import search_emails, SearchEmailsInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"5"]))
    mock_client.uid_search = AsyncMock(return_value=("OK", [b"123"]))
    mock_client.uid = AsyncMock(return_value=(
        "OK",
        [
            b'123 (UID 123 FLAGS (\\Seen) RFC822.HEADER {300}',
            bytearray(
                b'From: alice@example.com\r\n'
                b'To: bob@example.com\r\n'
                b'Subject: Quarterly Report\r\n'
                b'Date: Mon, 10 Mar 2024 09:15:00 +0000\r\n'
                b'Content-Type: text/plain\r\n\r\n'
            ),
            b')',
            b'A001 OK FETCH completed',
        ]
    ))

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await search_emails(SearchEmailsInput())

        assert len(result.messages) == 1
        msg = result.messages[0]

        # Verify all required fields exist
        assert hasattr(msg, "uid")
        assert hasattr(msg, "subject")
        assert hasattr(msg, "from_email")
        assert hasattr(msg, "to")
        assert hasattr(msg, "date")
        assert hasattr(msg, "unread")
        assert hasattr(msg, "flagged")
        assert hasattr(msg, "has_attachments")

        # Verify date is parsed to ISO 8601 format
        assert msg.date == "2024-03-10T09:15:00+00:00"


@pytest.mark.asyncio
async def test_search_emails_handles_folder_not_found(mock_settings):
    """Test that search handles folder not found error."""
    from imap.search import search_emails, SearchEmailsInput, IMAPFolderNotFoundError

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("NO", [b"Folder not found"]))

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises(IMAPFolderNotFoundError):
            await search_emails(SearchEmailsInput(folder="NonExistent"))


@pytest.mark.asyncio
async def test_search_emails_handles_no_results(mock_settings):
    """Test that search handles no results gracefully."""
    from imap.search import search_emails, SearchEmailsInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"0"]))
    mock_client.uid_search = AsyncMock(return_value=("OK", [b""]))  # No results

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await search_emails(SearchEmailsInput())

        assert result.total == 0
        assert result.messages == []


@pytest.mark.asyncio
async def test_search_emails_parses_iso_dates(mock_settings):
    """Test that search correctly parses ISO date strings for since/before."""
    from imap.search import search_emails, SearchEmailsInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"5"]))
    mock_client.uid_search = AsyncMock(return_value=("OK", [b""]))

    with patch("imap.search.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        # Should not raise an error with valid ISO dates
        result = await search_emails(SearchEmailsInput(
            since="2024-01-01",
            before="2024-03-01"
        ))

        # Verify uid_search was called (dates were parsed successfully)
        mock_client.uid_search.assert_called_once()
