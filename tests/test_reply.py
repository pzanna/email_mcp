"""Tests for reply_email tool."""

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


@pytest.mark.asyncio
async def test_reply_email_fetches_original(mock_settings):
    """Test that reply_email fetches the original message from IMAP."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    # Mock read_email to return original message
    original = ReadEmailResponse(
        uid="123",
        subject="Original Subject",
        from_email="alice@example.com",
        to=["bob@example.com"],
        cc=[],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Original body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to=None
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply@test.com>"

            await reply_email(ReplyEmailInput(uid="123", body="My reply"))

            # Verify read_email was called
            mock_read.assert_called_once()


@pytest.mark.asyncio
async def test_reply_email_reply_to_sender_only(mock_settings):
    """Test reply to sender only (reply_all=false)."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    original = ReadEmailResponse(
        uid="123",
        subject="Test",
        from_email="alice@example.com",
        to=["bob@example.com", "charlie@example.com"],
        cc=["david@example.com"],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to=None
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply@test.com>"

            await reply_email(ReplyEmailInput(uid="123", body="Reply", reply_all=False))

            # Verify send_message was called
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            # Should only have sender in To
            assert "alice@example.com" in msg["To"]
            assert "charlie@example.com" not in msg["To"]


@pytest.mark.asyncio
async def test_reply_email_reply_all(mock_settings):
    """Test reply to all (reply_all=true, includes Cc recipients)."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    original = ReadEmailResponse(
        uid="123",
        subject="Test",
        from_email="alice@example.com",
        to=["bob@example.com", "charlie@example.com"],
        cc=["david@example.com"],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to=None
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply@test.com>"

            await reply_email(ReplyEmailInput(uid="123", body="Reply", reply_all=True))

            # Verify send_message includes all original recipients
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            # Should include original sender + original To (excluding self)
            assert "alice@example.com" in msg["To"]
            assert "david@example.com" in msg["Cc"]


@pytest.mark.asyncio
async def test_reply_email_preserves_thread_headers(mock_settings):
    """Test that reply preserves In-Reply-To and References headers."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    original = ReadEmailResponse(
        uid="123",
        subject="Test",
        from_email="alice@example.com",
        to=["bob@example.com"],
        cc=[],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to="<prev@example.com>"
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply@test.com>"

            await reply_email(ReplyEmailInput(uid="123", body="Reply"))

            # Verify threading headers
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            assert msg["In-Reply-To"] == "<orig@example.com>"
            assert "<orig@example.com>" in msg["References"]


@pytest.mark.asyncio
async def test_reply_email_prefixes_subject_with_re(mock_settings):
    """Test that reply prefixes subject with 'Re: ' if not already present."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    original = ReadEmailResponse(
        uid="123",
        subject="Original Subject",
        from_email="alice@example.com",
        to=["bob@example.com"],
        cc=[],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to=None
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply@test.com>"

            await reply_email(ReplyEmailInput(uid="123", body="Reply"))

            msg = mock_send.call_args[0][0]
            assert msg["Subject"] == "Re: Original Subject"


@pytest.mark.asyncio
async def test_reply_email_returns_success_and_message_id(mock_settings):
    """Test that reply_email returns {success: true, message_id: ...}."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import ReadEmailResponse

    original = ReadEmailResponse(
        uid="123",
        subject="Test",
        from_email="alice@example.com",
        to=["bob@example.com"],
        cc=[],
        date="Mon, 10 Mar 2024 09:15:00 +0000",
        body_text="Body",
        body_html="",
        attachments=[],
        message_id="<orig@example.com>",
        in_reply_to=None
    )

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
            mock_read.return_value = original
            mock_send.return_value = "<reply123@test.com>"

            result = await reply_email(ReplyEmailInput(uid="123", body="Reply"))

            assert hasattr(result, "success")
            assert hasattr(result, "message_id")
            assert result.success is True
            assert result.message_id == "<reply123@test.com>"


@pytest.mark.asyncio
async def test_reply_email_handles_message_not_found(mock_settings):
    """Test that reply_email handles MESSAGE_NOT_FOUND if original UID doesn't exist."""
    from smtp.client import reply_email, ReplyEmailInput
    from imap.read import IMAPMessageNotFoundError

    with patch("imap.read.read_email", new_callable=AsyncMock) as mock_read:
        mock_read.side_effect = IMAPMessageNotFoundError("MESSAGE_NOT_FOUND: 999")

        with pytest.raises(IMAPMessageNotFoundError):
            await reply_email(ReplyEmailInput(uid="999", body="Reply"))
