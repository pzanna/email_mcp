"""Tests for send_email_with_attachments functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from email.message import EmailMessage

from smtp.attachments import send_email_with_attachments, SendEmailWithAttachmentsInput
from tools.mcp_routes import InvalidAttachmentPathError, AttachmentTooLargeError


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
    monkeypatch.setenv("MAX_ATTACHMENT_SIZE_MB", "50")

    import importlib
    import config
    importlib.reload(config)

    # Also reload smtp modules to pick up the new settings
    import smtp.client
    import smtp.attachments
    importlib.reload(smtp.client)
    importlib.reload(smtp.attachments)


@pytest.mark.asyncio
async def test_send_email_with_attachments_success(mock_settings):
    """Test successful email sending with attachments."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create test files
        test_file1 = Path(temp_workspace) / "test1.txt"
        test_file2 = Path(temp_workspace) / "test2.pdf"
        test_file1.write_text("Test content 1")
        test_file2.write_bytes(b"PDF content here")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024  # 100MB

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock) as mock_save:
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Test with attachments",
                    body="Please find attached files.",
                    attachment_paths=["test1.txt", "test2.pdf"]
                )

                result = await send_email_with_attachments(params)

                # Verify response
                assert result.success is True
                assert result.message_id == "<msg123@test.com>"
                assert len(result.attachments) == 2

                # Verify attachment metadata
                attachment1 = result.attachments[0]
                assert attachment1.filename == "test1.txt"
                assert attachment1.content_type == "text/plain"
                assert attachment1.size_bytes == len("Test content 1")

                attachment2 = result.attachments[1]
                assert attachment2.filename == "test2.pdf"
                assert attachment2.content_type == "application/pdf"
                assert attachment2.size_bytes == len(b"PDF content here")

                # Verify email was sent
                mock_send.assert_called_once()
                msg = mock_send.call_args[0][0]
                assert isinstance(msg, EmailMessage)
                assert msg["Subject"] == "Test with attachments"
                assert msg["To"] == "recipient@example.com"

                # Verify message has attachments
                assert msg.is_multipart()


@pytest.mark.asyncio
async def test_send_email_with_attachments_multipart_html(mock_settings):
    """Test sending multipart email (text + HTML) with attachments."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create test file
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Attachment content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="HTML email with attachment",
                    body="Plain text version",
                    body_html="<p>HTML version</p>",
                    attachment_paths=["test.txt"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                msg = mock_send.call_args[0][0]
                assert msg.is_multipart()


@pytest.mark.asyncio
async def test_send_email_with_attachments_multiple_recipients(mock_settings):
    """Test sending to multiple recipients with cc/bcc."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["to1@example.com", "to2@example.com"],
                    cc=["cc@example.com"],
                    bcc=["bcc@example.com"],
                    subject="Multiple recipients",
                    body="Body",
                    attachment_paths=["test.txt"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                msg = mock_send.call_args[0][0]
                assert "to1@example.com" in msg["To"]
                assert "to2@example.com" in msg["To"]
                assert msg["Cc"] == "cc@example.com"
                assert msg["Bcc"] == "bcc@example.com"


@pytest.mark.asyncio
async def test_send_email_with_attachments_custom_from_name(mock_settings):
    """Test custom from name override."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Custom from name",
                    body="Body",
                    from_name="Custom Sender",
                    attachment_paths=["test.txt"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                msg = mock_send.call_args[0][0]
                assert "Custom Sender" in msg["From"]


@pytest.mark.asyncio
async def test_send_email_with_attachments_absolute_path(mock_settings):
    """Test using absolute paths for attachments."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Absolute path",
                    body="Body",
                    attachment_paths=[str(test_file)]  # Use absolute path
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                assert len(result.attachments) == 1
                assert result.attachments[0].filename == "test.txt"


@pytest.mark.asyncio
async def test_send_email_with_attachments_path_outside_workspace(mock_settings):
    """Test security validation - path outside workspace should fail."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create file outside workspace
        with tempfile.TemporaryDirectory() as outside_workspace:
            outside_file = Path(outside_workspace) / "outside.txt"
            outside_file.write_text("Outside content")

            with patch('smtp.attachments.settings') as mock_settings_obj:
                mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
                mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Path outside workspace",
                    body="Body",
                    attachment_paths=[str(outside_file)]
                )

                with pytest.raises(InvalidAttachmentPathError):
                    await send_email_with_attachments(params)


@pytest.mark.asyncio
async def test_send_email_with_attachments_file_not_found(mock_settings):
    """Test error handling for missing attachment files."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            params = SendEmailWithAttachmentsInput(
                to=["recipient@example.com"],
                subject="Missing file",
                body="Body",
                attachment_paths=["nonexistent.txt"]
            )

            with pytest.raises(FileNotFoundError):
                await send_email_with_attachments(params)


@pytest.mark.asyncio
async def test_send_email_with_attachments_directory_path(mock_settings):
    """Test error handling when attachment path is a directory."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create a subdirectory
        subdir = Path(temp_workspace) / "subdir"
        subdir.mkdir()

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            params = SendEmailWithAttachmentsInput(
                to=["recipient@example.com"],
                subject="Directory path",
                body="Body",
                attachment_paths=["subdir"]
            )

            with pytest.raises(InvalidAttachmentPathError):
                await send_email_with_attachments(params)


@pytest.mark.asyncio
async def test_send_email_with_attachments_file_too_large(mock_settings):
    """Test size limit enforcement for individual files."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create large file
        large_file = Path(temp_workspace) / "large.txt"
        large_content = "x" * (60 * 1024 * 1024)  # 60MB
        large_file.write_text(large_content)

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.max_attachment_size_bytes = 50 * 1024 * 1024  # 50MB limit
            mock_settings_obj.MAX_ATTACHMENT_SIZE_MB = 50

            params = SendEmailWithAttachmentsInput(
                to=["recipient@example.com"],
                subject="Large file",
                body="Body",
                attachment_paths=["large.txt"]
            )

            with pytest.raises(AttachmentTooLargeError) as exc_info:
                await send_email_with_attachments(params)

            assert "exceeds limit" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_email_with_attachments_total_size_too_large(mock_settings):
    """Test total size limit enforcement for multiple files."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create multiple files that are individually under limit but exceed total
        file1 = Path(temp_workspace) / "file1.txt"
        file2 = Path(temp_workspace) / "file2.txt"
        file_content = "x" * (30 * 1024 * 1024)  # 30MB each
        file1.write_text(file_content)
        file2.write_text(file_content)

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.max_attachment_size_bytes = 50 * 1024 * 1024  # 50MB per file limit
            mock_settings_obj.MAX_ATTACHMENT_SIZE_MB = 50

            params = SendEmailWithAttachmentsInput(
                to=["recipient@example.com"],
                subject="Multiple large files",
                body="Body",
                attachment_paths=["file1.txt", "file2.txt"]  # Total: 60MB, limit is 100MB (2x50MB)
            )

            # This should not raise since total is 60MB < 100MB limit
            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                result = await send_email_with_attachments(params)
                assert result.success is True

            # Now test with a file that would exceed the total limit
            file3 = Path(temp_workspace) / "file3.txt"
            file3_content = "x" * (45 * 1024 * 1024)  # 45MB
            file3.write_text(file3_content)

            params_too_large = SendEmailWithAttachmentsInput(
                to=["recipient@example.com"],
                subject="Too many large files",
                body="Body",
                attachment_paths=["file1.txt", "file2.txt", "file3.txt"]  # Total: 105MB > 100MB limit
            )

            with pytest.raises(AttachmentTooLargeError) as exc_info:
                await send_email_with_attachments(params_too_large)

            assert "Total attachments size" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_email_with_attachments_mime_type_detection(mock_settings):
    """Test MIME type detection for various file types."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        # Create files with different extensions
        txt_file = Path(temp_workspace) / "doc.txt"
        pdf_file = Path(temp_workspace) / "doc.pdf"
        jpg_file = Path(temp_workspace) / "image.jpg"
        unknown_file = Path(temp_workspace) / "unknown.unknown"

        txt_file.write_text("Text content")
        pdf_file.write_bytes(b"PDF content")
        jpg_file.write_bytes(b"JPG content")
        unknown_file.write_bytes(b"Unknown content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="MIME type test",
                    body="Body",
                    attachment_paths=["doc.txt", "doc.pdf", "image.jpg", "unknown.unknown"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                assert len(result.attachments) == 4

                # Check MIME types
                mime_types = {att.filename: att.content_type for att in result.attachments}
                assert mime_types["doc.txt"] == "text/plain"
                assert mime_types["doc.pdf"] == "application/pdf"
                assert mime_types["image.jpg"] == "image/jpeg"
                assert mime_types["unknown.unknown"] == "application/octet-stream"  # Default for unknown


@pytest.mark.asyncio
async def test_send_email_with_attachments_saves_to_sent(mock_settings):
    """Test that sent email is saved to IMAP Sent folder."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock) as mock_save:
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Save to sent test",
                    body="Body",
                    attachment_paths=["test.txt"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_with_attachments_save_to_sent_failure_nonfatal(mock_settings):
    """Test that _save_to_sent failure doesn't prevent successful send."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock) as mock_save:
                mock_send.return_value = "<msg123@test.com>"
                mock_save.side_effect = Exception("IMAP failure")

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Save failure test",
                    body="Body",
                    attachment_paths=["test.txt"]
                )

                # Should not raise - save failure is non-fatal
                result = await send_email_with_attachments(params)

                assert result.success is True
                assert result.message_id == "<msg123@test.com>"


@pytest.mark.asyncio
async def test_send_email_with_attachments_sets_headers(mock_settings):
    """Test that proper email headers are set."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Content")

        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.SMTP_USER = "test@test.com"
            mock_settings_obj.DEFAULT_FROM_NAME = "Test User"
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            with patch('smtp.attachments.send_message', new_callable=AsyncMock) as mock_send, \
                 patch('smtp.attachments._save_to_sent', new_callable=AsyncMock):
                mock_send.return_value = "<msg123@test.com>"

                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Header test",
                    body="Body",
                    attachment_paths=["test.txt"]
                )

                result = await send_email_with_attachments(params)

                assert result.success is True
                msg = mock_send.call_args[0][0]

                # Check required headers
                assert msg["Message-ID"] is not None
                assert msg["Date"] is not None
                assert msg["From"] is not None
                assert msg["To"] == "recipient@example.com"
                assert msg["Subject"] == "Header test"


@pytest.mark.asyncio
async def test_send_email_with_attachments_path_traversal_security(mock_settings):
    """Test security against path traversal attacks."""
    with tempfile.TemporaryDirectory() as temp_workspace:
        with patch('smtp.attachments.settings') as mock_settings_obj:
            mock_settings_obj.EMAIL_BASE_DIR = temp_workspace
            mock_settings_obj.max_attachment_size_bytes = 100 * 1024 * 1024

            # Test various path traversal attempts
            dangerous_paths = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "/etc/shadow",
                "C:\\Windows\\System32\\config\\SAM"
            ]

            for dangerous_path in dangerous_paths:
                params = SendEmailWithAttachmentsInput(
                    to=["recipient@example.com"],
                    subject="Path traversal test",
                    body="Body",
                    attachment_paths=[dangerous_path]
                )

                with pytest.raises((InvalidAttachmentPathError, FileNotFoundError)):
                    await send_email_with_attachments(params)