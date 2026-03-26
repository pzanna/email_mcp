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


def _uid_ok(*args, **kwargs):
    """Default UID command handler — returns OK for any command."""
    return ("OK", [b"1 (FLAGS (\\Seen))"])


def _uid_no_move_capability(*args, **kwargs):
    """Simulate UID MOVE raising 'server has not MOVE capability'."""
    cmd = args[0] if args else ""
    if cmd == "MOVE":
        raise Exception("server has not MOVE capability")
    return ("OK", [b"1 (FLAGS (\\Deleted))"])


# Tests for mark_email
@pytest.mark.asyncio
async def test_mark_email_set_read_true(mock_settings):
    """Test setting read=true on a message (adds \\Seen flag)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=True))

        assert result.success is True
        # Verify uid() was called with STORE, the UID, and +FLAGS
        mock_client.uid.assert_called_once()
        call_args = mock_client.uid.call_args[0]
        assert call_args[0] == "STORE"
        assert "123" in call_args
        assert "+FLAGS" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_read_false(mock_settings):
    """Test setting read=false (removes \\Seen flag)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS ())"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=False))

        assert result.success is True
        mock_client.uid.assert_called_once()
        call_args = mock_client.uid.call_args[0]
        assert call_args[0] == "STORE"
        assert "-FLAGS" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_flagged_true(mock_settings):
    """Test setting flagged=true (adds \\Flagged)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Flagged))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", flagged=True))

        assert result.success is True
        mock_client.uid.assert_called_once()
        call_args = mock_client.uid.call_args[0]
        assert call_args[0] == "STORE"
        assert "+FLAGS" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_flagged_false(mock_settings):
    """Test setting flagged=false (removes \\Flagged)."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS ())"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", flagged=False))

        assert result.success is True
        mock_client.uid.assert_called_once()
        call_args = mock_client.uid.call_args[0]
        assert call_args[0] == "STORE"
        assert "-FLAGS" in call_args


@pytest.mark.asyncio
async def test_mark_email_set_both_flags(mock_settings):
    """Test setting both read and flagged in one call."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen \\Flagged))"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await mark_email(MarkEmailInput(uid="123", read=True, flagged=True))

        assert result.success is True
        # Should have been called twice (once for read, once for flagged)
        assert mock_client.uid.call_count == 2


@pytest.mark.asyncio
async def test_mark_email_returns_success_true(mock_settings):
    """Test that mark_email returns {success: true}."""
    from imap.flags import mark_email, MarkEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"1 (FLAGS (\\Seen))"]))

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
    mock_client.uid = AsyncMock(return_value=("NO", [b"Message not found"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        from imap.flags import IMAPMessageNotFoundError
        with pytest.raises(IMAPMessageNotFoundError):
            await mark_email(MarkEmailInput(uid="999", read=True))


# Tests for move_email
def _no_move_capability(*args, **kwargs):
    """Simulate UID MOVE raising 'server has not MOVE capability'."""
    raise Exception("server has not MOVE capability")


@pytest.mark.asyncio
async def test_move_email_uses_move_when_available(mock_settings):
    """Test that move_email uses RFC 6851 UID MOVE when the server supports it."""
    from imap.flags import move_email, MoveEmailInput

    move_responses = {
        "MOVE": ("OK", [b"OK [COPYUID 1 123 456]"]),
    }

    async def uid_router(cmd, *args, **kwargs):
        return move_responses.get(cmd, ("OK", [b"OK"]))

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(side_effect=uid_router)
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        assert result.success is True
        # Only MOVE was called — no COPY or STORE
        commands_called = [c[0][0] for c in mock_client.uid.call_args_list]
        assert "MOVE" in commands_called
        assert "COPY" not in commands_called
        assert "STORE" not in commands_called
        mock_client.expunge.assert_not_called()


@pytest.mark.asyncio
async def test_move_email_moves_message(mock_settings):
    """Test moving message via UID COPY+DELETE fallback when MOVE not supported."""
    from imap.flags import move_email, MoveEmailInput

    async def uid_router(cmd, *args, **kwargs):
        if cmd == "MOVE":
            raise Exception("server has not MOVE capability")
        if cmd == "COPY":
            return ("OK", [b"OK [COPYUID 1 123 456]"])
        if cmd == "STORE":
            return ("OK", [b"1 (FLAGS (\\Deleted))"])
        return ("OK", [b"OK"])

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(side_effect=uid_router)
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        assert result.success is True
        commands_called = [c[0][0] for c in mock_client.uid.call_args_list]
        assert "COPY" in commands_called
        assert "STORE" in commands_called
        mock_client.expunge.assert_called_once()


@pytest.mark.asyncio
async def test_move_email_returns_new_uid(mock_settings):
    """Test that move_email returns new_uid from MOVEUID response."""
    from imap.flags import move_email, MoveEmailInput

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(return_value=("OK", [b"OK [MOVEUID 1 123 456]"]))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        result = await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        assert result.success is True
        assert hasattr(result, "new_uid")
        assert result.new_uid == "456"


@pytest.mark.asyncio
async def test_move_email_handles_folder_not_found(mock_settings):
    """Test that move_email handles FOLDER_NOT_FOUND for destination."""
    from imap.flags import move_email, MoveEmailInput, IMAPFolderNotFoundError

    async def uid_router(cmd, *args, **kwargs):
        if cmd == "MOVE":
            raise Exception("server has not MOVE capability")
        return ("NO", [b"[TRYCREATE] Folder not found"])

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(side_effect=uid_router)

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises(IMAPFolderNotFoundError):
            await move_email(MoveEmailInput(uid="123", to_folder="NonExistent"))


@pytest.mark.asyncio
async def test_move_email_handles_message_not_found(mock_settings):
    """Test that move_email handles MESSAGE_NOT_FOUND if UID doesn't exist."""
    from imap.flags import move_email, MoveEmailInput, IMAPMessageNotFoundError, IMAPFolderNotFoundError

    async def uid_router(cmd, *args, **kwargs):
        if cmd == "MOVE":
            raise Exception("server has not MOVE capability")
        return ("NO", [b"Message not found"])

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(side_effect=uid_router)

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        with pytest.raises((IMAPMessageNotFoundError, IMAPFolderNotFoundError)):
            await move_email(MoveEmailInput(uid="999", to_folder="Archive"))


@pytest.mark.asyncio
async def test_move_email_deletes_source_message(mock_settings):
    """Test that move_email marks source as deleted and expunges (COPY fallback)."""
    from imap.flags import move_email, MoveEmailInput

    async def uid_router(cmd, *args, **kwargs):
        if cmd == "MOVE":
            raise Exception("server has not MOVE capability")
        if cmd == "COPY":
            return ("OK", [b"OK"])
        if cmd == "STORE":
            return ("OK", [b"1 (FLAGS (\\Deleted))"])
        return ("OK", [b"OK"])

    mock_client = AsyncMock()
    mock_client.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_client.uid = AsyncMock(side_effect=uid_router)
    mock_client.expunge = AsyncMock(return_value=("OK", []))

    with patch("imap.flags.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        await move_email(MoveEmailInput(uid="123", to_folder="Archive"))

        # Verify deletion workflow
        store_calls = [c for c in mock_client.uid.call_args_list if c[0][0] == "STORE"]
        assert len(store_calls) == 1
        store_args = store_calls[0][0]
        assert "\\Deleted" in str(store_args)

        mock_client.expunge.assert_called_once()
