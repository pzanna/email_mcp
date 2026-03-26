"""Tests for list_folders tool."""

import pytest
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

    # Reload modules
    import importlib
    import config
    importlib.reload(config)


@pytest.mark.asyncio
async def test_list_folders_returns_folder_list(mock_settings):
    """Test that list_folders returns a list of folders with correct schema."""
    from imap.read import list_folders

    # Mock IMAP client
    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Sent"',
            b'(\\HasNoChildren) "/" "Drafts"',
        ]
    ))

    # Mock the pool
    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await list_folders()

        assert result.folders is not None
        assert len(result.folders) == 3
        assert result.folders[0].name == "INBOX"
        assert result.folders[0].delimiter == "/"
        assert "\\HasNoChildren" in result.folders[0].flags
        assert result.folders[1].name == "Sent"
        assert result.folders[2].name == "Drafts"


@pytest.mark.asyncio
async def test_list_folders_handles_no_folders(mock_settings):
    """Test that list_folders handles IMAP server returning no folders."""
    from imap.read import list_folders

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=("OK", []))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await list_folders()

        assert result.folders == []


@pytest.mark.asyncio
async def test_list_folders_handles_connection_failure(mock_settings):
    """Test that list_folders handles IMAP connection failures gracefully."""
    from imap.read import list_folders
    from imap.client import IMAPConnectionError

    # Mock pool to raise connection error
    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.side_effect = IMAPConnectionError("Connection timeout")

        with pytest.raises(IMAPConnectionError):
            await list_folders()


@pytest.mark.asyncio
async def test_list_folders_returns_correct_json_schema(mock_settings):
    """Test that list_folders returns data matching the spec schema."""
    from imap.read import list_folders, FolderInfo, ListFoldersResponse

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [b'(\\HasNoChildren \\Marked) "/" "INBOX"']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await list_folders()

        # Verify it's a ListFoldersResponse
        assert isinstance(result, ListFoldersResponse)
        assert hasattr(result, "folders")

        # Verify folders are FolderInfo objects
        assert len(result.folders) == 1
        assert isinstance(result.folders[0], FolderInfo)
        assert hasattr(result.folders[0], "name")
        assert hasattr(result.folders[0], "delimiter")
        assert hasattr(result.folders[0], "flags")

        # Verify field types
        assert isinstance(result.folders[0].name, str)
        assert isinstance(result.folders[0].delimiter, str)
        assert isinstance(result.folders[0].flags, list)
        assert all(isinstance(flag, str) for flag in result.folders[0].flags)


@pytest.mark.asyncio
async def test_list_folders_parses_flags_correctly(mock_settings):
    """Test that list_folders correctly parses folder flags."""
    from imap.read import list_folders

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasChildren \\Noselect) "/" "Parent"',
            b'(\\Marked \\Flagged) "/" "Important"',
        ]
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await list_folders()

        # Check flags parsing
        assert result.folders[0].flags == ["\\HasNoChildren"]
        assert set(result.folders[1].flags) == {"\\HasChildren", "\\Noselect"}
        assert set(result.folders[2].flags) == {"\\Marked", "\\Flagged"}


# Tests for read_email tool
@pytest.mark.asyncio
async def test_read_email_fetches_full_message(mock_settings):
    """Test that read_email fetches full message by UID."""
    from imap.read import read_email, ReadEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))

    # Mock email with all fields
    email_content = b"""From: alice@example.com
To: bob@example.com
Cc: charlie@example.com
Subject: Test Email
Date: Mon, 10 Mar 2024 09:15:00 +0000
Message-ID: <msg123@example.com>
In-Reply-To: <prev@example.com>
Content-Type: text/plain; charset=utf-8

This is the email body.
"""

    mock_client.fetch = AsyncMock(return_value=(
        "OK",
        [(b'1 (UID 123 RFC822 {300}', email_content), b')']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await read_email(ReadEmailInput(uid="123"))

        assert result.uid == "123"
        assert result.subject == "Test Email"
        assert result.from_email == "alice@example.com"
        assert "bob@example.com" in result.to
        assert "charlie@example.com" in result.cc
        assert result.message_id == "<msg123@example.com>"
        assert result.in_reply_to == "<prev@example.com>"


@pytest.mark.asyncio
async def test_read_email_returns_all_required_fields(mock_settings):
    """Test that read_email returns all fields per spec."""
    from imap.read import read_email, ReadEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))

    email_content = b"""From: test@test.com
To: user@test.com
Subject: Test
Date: Mon, 10 Mar 2024 09:15:00 +0000
Message-ID: <test@test.com>
Content-Type: text/plain

Body text.
"""

    mock_client.fetch = AsyncMock(return_value=(
        "OK",
        [(b'1 (RFC822 {100}', email_content), b')']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await read_email(ReadEmailInput(uid="123"))

        # Verify all required fields exist
        assert hasattr(result, "uid")
        assert hasattr(result, "subject")
        assert hasattr(result, "from_email")
        assert hasattr(result, "to")
        assert hasattr(result, "cc")
        assert hasattr(result, "date")
        assert hasattr(result, "body_text")
        assert hasattr(result, "body_html")
        assert hasattr(result, "attachments")
        assert hasattr(result, "in_reply_to")
        assert hasattr(result, "message_id")


@pytest.mark.asyncio
async def test_read_email_attachment_metadata(mock_settings):
    """Test that read_email returns attachment metadata (no binary)."""
    from imap.read import read_email, ReadEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))

    # Multipart email with attachment
    email_content = b"""From: test@test.com
To: user@test.com
Subject: With Attachment
Date: Mon, 10 Mar 2024 09:15:00 +0000
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Body text.

--boundary123
Content-Type: application/pdf; name="report.pdf"
Content-Disposition: attachment; filename="report.pdf"
Content-Transfer-Encoding: base64

[base64 data here]
--boundary123--
"""

    mock_client.fetch = AsyncMock(return_value=(
        "OK",
        [(b'1 (RFC822 {500}', email_content), b')']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await read_email(ReadEmailInput(uid="123"))

        assert len(result.attachments) > 0
        attachment = result.attachments[0]

        # Verify attachment metadata fields
        assert hasattr(attachment, "filename")
        assert hasattr(attachment, "content_type")
        assert hasattr(attachment, "size_bytes")
        assert "report.pdf" in attachment.filename or attachment.filename == "report.pdf"


@pytest.mark.asyncio
async def test_read_email_handles_message_not_found(mock_settings):
    """Test that read_email handles MESSAGE_NOT_FOUND."""
    from imap.read import read_email, ReadEmailInput, IMAPMessageNotFoundError

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.fetch = AsyncMock(return_value=("NO", [b"Message not found"]))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises(IMAPMessageNotFoundError):
            await read_email(ReadEmailInput(uid="999"))


@pytest.mark.asyncio
async def test_read_email_handles_multipart_message(mock_settings):
    """Test that read_email extracts text and HTML parts from multipart."""
    from imap.read import read_email, ReadEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))

    email_content = b"""From: test@test.com
To: user@test.com
Subject: Multipart Test
Date: Mon, 10 Mar 2024 09:15:00 +0000
Content-Type: multipart/alternative; boundary="alt123"

--alt123
Content-Type: text/plain

Plain text body.

--alt123
Content-Type: text/html

<p>HTML body.</p>

--alt123--
"""

    mock_client.fetch = AsyncMock(return_value=(
        "OK",
        [(b'1 (RFC822 {400}', email_content), b')']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await read_email(ReadEmailInput(uid="123"))

        # Should have both text and HTML
        assert result.body_text is not None
        assert result.body_html is not None
        assert "Plain text body" in result.body_text or len(result.body_text) > 0


@pytest.mark.asyncio
async def test_read_email_handles_plain_text_only(mock_settings):
    """Test that read_email handles plain text messages (body_html empty)."""
    from imap.read import read_email, ReadEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))

    email_content = b"""From: test@test.com
To: user@test.com
Subject: Plain Text Only
Date: Mon, 10 Mar 2024 09:15:00 +0000
Content-Type: text/plain

Just plain text.
"""

    mock_client.fetch = AsyncMock(return_value=(
        "OK",
        [(b'1 (RFC822 {200}', email_content), b')']
    ))

    with patch("imap.read.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await read_email(ReadEmailInput(uid="123"))

        assert result.body_text is not None
        assert result.body_html == "" or result.body_html is None
