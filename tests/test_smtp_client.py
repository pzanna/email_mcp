"""Tests for SMTP client."""

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
async def test_smtp_connection_with_starttls(mock_settings):
    """Test that SMTP connection succeeds with STARTTLS."""
    from smtp.client import send_message

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        await send_message(msg)

        # Verify STARTTLS mode is passed to connect
        mock_smtp.connect.assert_called_once_with(start_tls=True)
        mock_smtp.starttls.assert_not_called()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_connection_with_starttls_auto_mode(mock_settings, monkeypatch):
    """Test that SMTP connection uses start_tls=None in auto mode."""
    import smtp.client as smtp_client

    monkeypatch.setattr(smtp_client.settings, "SMTP_STARTTLS", "none")

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        await smtp_client.send_message(msg)

        mock_smtp.connect.assert_called_once_with(start_tls=None)
        mock_smtp.starttls.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_connection_with_starttls_disabled(mock_settings, monkeypatch):
    """Test that SMTP connection uses start_tls=False when disabled."""
    import smtp.client as smtp_client

    monkeypatch.setattr(smtp_client.settings, "SMTP_STARTTLS", "false")

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        await smtp_client.send_message(msg)

        mock_smtp.connect.assert_called_once_with(start_tls=False)
        mock_smtp.starttls.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_authentication_works(mock_settings):
    """Test that authentication works with provided credentials."""
    from smtp.client import send_message

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        await send_message(msg)

        # Verify login was called with credentials
        mock_smtp.login.assert_called_once_with("test@test.com", "test123")


@pytest.mark.asyncio
async def test_smtp_send_returns_message_id(mock_settings):
    """Test that send() sends a message and returns message_id."""
    from smtp.client import send_message

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg["Message-ID"] = "<test123@example.com>"
        msg.set_content("Body")

        message_id = await send_message(msg)

        # Verify message_id is returned
        assert message_id == "<test123@example.com>"


@pytest.mark.asyncio
async def test_smtp_handles_auth_failed(mock_settings):
    """Test that SMTP handles SMTP_AUTH_FAILED on bad credentials."""
    from smtp.client import send_message, SMTPAuthError

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock(side_effect=Exception("Authentication failed"))

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        with pytest.raises(SMTPAuthError):
            await send_message(msg)


@pytest.mark.asyncio
async def test_smtp_handles_send_failed(mock_settings):
    """Test that SMTP handles SEND_FAILED on delivery errors."""
    from smtp.client import send_message, SMTPSendError

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock(side_effect=Exception("Delivery failed"))

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        with pytest.raises(SMTPSendError):
            await send_message(msg)


@pytest.mark.asyncio
async def test_smtp_connection_is_closed(mock_settings):
    """Test that connection is closed after send."""
    from smtp.client import send_message

    mock_smtp = AsyncMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.starttls = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.send_message = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with patch("smtp.client.SMTP", return_value=mock_smtp):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "test@test.com"
        msg["To"] = "user@test.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")

        await send_message(msg)

        # Verify quit was called to close connection
        mock_smtp.quit.assert_called_once()
