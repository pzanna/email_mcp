"""Tests for mark_email and move_email tools."""

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

    import importlib
    import config
    importlib.reload(config)


# Tests for mark_email
@pytest.mark.asyncio
async def test_mark_email_set_read_true(mock_settings):
    """Test setting read=true on a message (adds \\Seen flag)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=True))

        assert result.success is True
        # Verify store was called with +FLAGS \Seen
        mock_client.store.assert_called_once()
        call_args = mock_client.store.call_args[0]
        assert "123" in call_args
        assert "+FLAGS" in call_args or "+FLAGS.SILENT" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_read_false(mock_settings):
    """Test setting read=false (removes \\Seen flag)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS ())"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=False))

        assert result.success is True
        # Verify store was called with -FLAGS \Seen
        mock_client.store.assert_called_once()
        call_args = mock_client.store.call_args[0]
        assert "-FLAGS" in call_args or "-FLAGS.SILENT" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_flagged_true(mock_settings):
    """Test setting flagged=true (adds \\Flagged)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Flagged))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", flagged=True))

        assert result.success is True
        mock_client.store.assert_called_once()


@pytest.mark.asyncio
async def test_mark_email_set_flagged_false(mock_settings):
    """Test setting flagged=false (removes \\Flagged)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS ())"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", flagged=False))

        assert result.success is True


@pytest.mark.asyncio
async def test_mark_email_set_both_flags(mock_settings):
    """Test setting both read and flagged in one call."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen \\Flagged))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=True, flagged=True))

        assert result.success is True
        # Should have been called twice (once for each flag)
        assert mock_client.store.call_count >= 1


@pytest.mark.asyncio
async def test_mark_email_returns_success_true(mock_settings):
    """Test that mark_email returns {success: true}."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=True))

        assert hasattr(result, "success")
        assert result.success is True


@pytest.mark.asyncio
async def test_mark_email_handles_message_not_found(mock_settings):
    """Test that mark_email handles MESSAGE_NOT_FOUND if UID doesn't exist."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.store = AsyncMock(return_value=("NO", [b"Message not found"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        # Should raise an error or return success=False
        from imap.flags import IMAPMessageNotFoundError
        with pytest.raises(IMAPMessageNotFoundError):
            await mark_email(MarkEmailInput(uid="999", read=True))


# Tests for move_email
@pytest.mark.asyncio
async def test_move_email_moves_message(mock_settings):
    """Test moving message from one folder to another."""
    from imap.flags import move_email, MoveEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.copy = AsyncMock(return_value=("OK", [b"OK [COPYUID 1 123 456]"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Deleted))"]))
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        assert result.success is True
        # Verify copy was called
        mock_client.copy.assert_called_once()
        # Verify store was called to mark as deleted
        mock_client.store.assert_called_once()
        # Verify expunge was called
        mock_client.expunge.assert_called_once()


@pytest.mark.asyncio
async def test_move_email_returns_new_uid(mock_settings):
    """Test that move_email returns new_uid if available."""
    from imap.flags import move_email, MoveEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.copy = AsyncMock(return_value=("OK", [b"OK [COPYUID 1 123 456]"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Deleted))"]))
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        assert result.success is True
        # new_uid may or may not be present depending on server
        assert hasattr(result, "new_uid")


@pytest.mark.asyncio
async def test_move_email_handles_folder_not_found(mock_settings):
    """Test that move_email handles FOLDER_NOT_FOUND for destination."""
    from imap.flags import move_email, MoveEmailInput, IMAPFolderNotFoundError

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.copy = AsyncMock(return_value=("NO", [b"[TRYCREATE] Folder not found"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises(IMAPFolderNotFoundError):
            await move_email(MoveEmailInput(uid="123", to_folder="NonExistent"))


@pytest.mark.asyncio
async def test_move_email_handles_message_not_found(mock_settings):
    """Test that move_email handles MESSAGE_NOT_FOUND if UID doesn't exist."""
    from imap.flags import move_email, MoveEmailInput, IMAPMessageNotFoundError, IMAPFolderNotFoundError

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.copy = AsyncMock(return_value=("NO", [b"Message not found"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises((IMAPMessageNotFoundError, IMAPFolderNotFoundError)):
            await move_email(MoveEmailInput(uid="999", to_folder="Archive"))


@pytest.mark.asyncio
async def test_move_email_deletes_source_message(mock_settings):
    """Test that move_email marks source as deleted and expunges."""
    from imap.flags import move_email, MoveEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.copy = AsyncMock(return_value=("OK", [b"OK"]))
    mock_client.store = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Deleted))"]))
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        # Verify deletion workflow
        mock_client.store.assert_called_once()
        store_call = mock_client.store.call_args[0]
        assert "\\Deleted" in str(store_call)

        mock_client.expunge.assert_called_once()
