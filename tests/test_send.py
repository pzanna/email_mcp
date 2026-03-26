"""Tests for send_email and reply_email tools."""

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
    monkeypatch.setenv("DEFAULT_FROM_NAME", "Test User")

    import importlib
    import config
    importlib.reload(config)

    # Also reload smtp.client to pick up the new settings
    import smtp.client
    importlib.reload(smtp.client)


# Tests for send_email
@pytest.mark.asyncio
async def test_send_email_plain_text(mock_settings):
    """Test sending plain text email with required fields."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<msg123@test.com>"

        result = await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test Email",
            body="This is a test."
        ))

        assert result.success is True
        assert result.message_id == "<msg123@test.com>"
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_multipart(mock_settings):
    """Test sending multipart email (body_text + body_html)."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<msg123@test.com>"

        result = await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test Email",
            body="Plain text",
            body_html="<p>HTML version</p>"
        ))

        assert result.success is True
        # Verify multipart message was created
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert msg.is_multipart()


@pytest.mark.asyncio
async def test_send_email_multiple_recipients(mock_settings):
    """Test handling multiple recipients in to, cc, bcc."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<msg123@test.com>"

        result = await send_email(SendEmailInput(
            to=["user1@example.com", "user2@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Test Email",
            body="Body"
        ))

        assert result.success is True
        msg = mock_send.call_args[0][0]
        assert "user1@example.com" in msg["To"]
        assert "user2@example.com" in msg["To"]


@pytest.mark.asyncio
async def test_send_email_uses_default_from_name(mock_settings):
    """Test that DEFAULT_FROM_NAME is used if from_name not provided."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<msg123@test.com>"

        await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test",
            body="Body"
        ))

        msg = mock_send.call_args[0][0]
        # Should use DEFAULT_FROM_NAME from config
        assert "Test User" in msg["From"]


@pytest.mark.asyncio
async def test_send_email_custom_from_name(mock_settings):
    """Test that custom from_name overrides DEFAULT_FROM_NAME."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<msg123@test.com>"

        await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test",
            body="Body",
            from_name="Custom Name"
        ))

        msg = mock_send.call_args[0][0]
        assert "Custom Name" in msg["From"]


@pytest.mark.asyncio
async def test_send_email_returns_success_and_message_id(mock_settings):
    """Test that send_email returns {success: true, message_id: ...}."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "<unique123@test.com>"

        result = await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test",
            body="Body"
        ))

        assert hasattr(result, "success")
        assert hasattr(result, "message_id")
        assert result.success is True
        assert result.message_id == "<unique123@test.com>"


@pytest.mark.asyncio
async def test_send_email_handles_send_failed(mock_settings):
    """Test that send_email handles SEND_FAILED error."""
    from smtp.client import send_email, SendEmailInput, SMTPSendError

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = SMTPSendError("Delivery failed")

        with pytest.raises(SMTPSendError):
            await send_email(SendEmailInput(
                to=["user@example.com"],
                subject="Test",
                body="Body"
            ))


@pytest.mark.asyncio
async def test_send_email_saves_to_sent_folder(mock_settings):
    """Test that send_email calls _save_to_sent after a successful send."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send, \
         patch("smtp.client._save_to_sent", new_callable=AsyncMock) as mock_save:
        mock_send.return_value = "<msg123@test.com>"

        result = await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test",
            body="Body"
        ))

        assert result.success is True
        # _save_to_sent must be called exactly once with the composed EmailMessage
        mock_save.assert_called_once()
        msg_arg = mock_save.call_args[0][0]
        assert msg_arg["Subject"] == "Test"


@pytest.mark.asyncio
async def test_send_email_does_not_fail_when_save_to_sent_errors(mock_settings):
    """Test that send_email succeeds even if _save_to_sent raises an exception."""
    from smtp.client import send_email, SendEmailInput

    with patch("smtp.client.send_message", new_callable=AsyncMock) as mock_send, \
         patch("smtp.client._save_to_sent", new_callable=AsyncMock) as mock_save:
        mock_send.return_value = "<msg123@test.com>"
        mock_save.side_effect = Exception("IMAP unavailable")

        # Should not raise — save failure is non-fatal
        result = await send_email(SendEmailInput(
            to=["user@example.com"],
            subject="Test",
            body="Body"
        ))

        assert result.success is True
        assert result.message_id == "<msg123@test.com>"


@pytest.mark.asyncio
async def test_save_to_sent_appends_via_imap(mock_settings):
    """Test that _save_to_sent discovers the Sent folder and calls IMAP APPEND."""
    from email.message import EmailMessage
    from smtp.client import _save_to_sent

    msg = EmailMessage()
    msg["From"] = "test@test.com"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Saved to Sent"
    msg.set_content("Body")

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Sent) "/" "Sent"',
        ]
    ))
    mock_client.append = AsyncMock(return_value=("OK", [b"APPEND complete"]))

    with patch("smtp.client.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        await _save_to_sent(msg)

        mock_client.append.assert_called_once()
        call_args = mock_client.append.call_args[0]
        assert call_args[0] == "Sent"       # correct folder name
        assert isinstance(call_args[1], bytes)  # raw message bytes


@pytest.mark.asyncio
async def test_save_to_sent_falls_back_to_common_name(mock_settings):
    """Test that _save_to_sent falls back to 'Sent Messages' when no \\Sent flag."""
    from email.message import EmailMessage
    from smtp.client import _save_to_sent

    msg = EmailMessage()
    msg["From"] = "test@test.com"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Fallback test"
    msg.set_content("Body")

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Sent Messages"',
        ]
    ))
    mock_client.append = AsyncMock(return_value=("OK", [b"APPEND complete"]))

    with patch("smtp.client.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        await _save_to_sent(msg)

        mock_client.append.assert_called_once()
        assert mock_client.append.call_args[0][0] == "Sent Messages"


@pytest.mark.asyncio
async def test_save_to_sent_skips_gracefully_when_no_sent_folder(mock_settings):
    """Test that _save_to_sent logs and returns without error when no Sent folder found."""
    from email.message import EmailMessage
    from smtp.client import _save_to_sent

    msg = EmailMessage()
    msg["From"] = "test@test.com"
    msg["To"] = "user@example.com"
    msg["Subject"] = "No sent folder"
    msg.set_content("Body")

    mock_client = AsyncMock()
    mock_client.list = AsyncMock(return_value=(
        "OK",
        [b'(\\HasNoChildren) "/" "INBOX"']
    ))
    mock_client.append = AsyncMock()

    with patch("smtp.client.imap_pool") as mock_pool:
        mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

        # Must not raise
        await _save_to_sent(msg)

        # append should NOT have been called
        mock_client.append.assert_not_called()
