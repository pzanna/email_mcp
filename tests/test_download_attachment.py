"""Tests for download_attachment functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from email.message import EmailMessage
import email.mime.multipart
import email.mime.text
import email.mime.application

from imap.attachments import download_attachment, DownloadAttachmentInput
from tools.mcp_routes import AttachmentNotFoundError, AttachmentTooLargeError


@pytest.mark.asyncio
async def test_download_attachment_success():
    """Test successful attachment download."""
    # Create mock email with attachment
    msg = email.mime.multipart.MIMEMultipart()
    msg['Subject'] = 'Test with attachment'

    # Add text part
    text_part = email.mime.text.MIMEText('Email body')
    msg.attach(text_part)

    # Add attachment
    pdf_data = b'%PDF-1.4 fake pdf content'
    attachment = email.mime.application.MIMEApplication(pdf_data, _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='test.pdf')
    msg.attach(attachment)

    with tempfile.TemporaryDirectory() as temp_workspace:
        with patch('imap.attachments.settings') as mock_settings:
            mock_settings.EMAIL_BASE_DIR = temp_workspace
            mock_settings.max_attachment_size_bytes = 100 * 1024 * 1024  # 100MB
            mock_settings.download_dir = Path(temp_workspace) / "attachments" / "email" / "downloads"

            with patch('imap.attachments.read_email') as mock_read_email:
                from imap.read import ReadEmailResponse, AttachmentInfo

                # Mock the read_email response
                mock_read_email.return_value = ReadEmailResponse(
                    uid="123",
                    subject="Test with attachment",
                    from_email="sender@example.com",
                    to=["recipient@example.com"],
                    cc=[],
                    date="2024-01-01T00:00:00",
                    body_text="Email body",
                    body_html="",
                    attachments=[
                        AttachmentInfo(
                            filename="test.pdf",
                            content_type="application/pdf",
                            size_bytes=len(pdf_data)
                        )
                    ],
                    in_reply_to=None,
                    message_id="<123@example.com>"
                )

                with patch('imap.attachments.imap_pool') as mock_pool:
                    mock_client = AsyncMock()
                    mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

                    # Mock IMAP responses
                    mock_client.select.return_value = ("OK", [])
                    mock_client.uid.return_value = ("OK", [
                        b'1 FETCH (RFC822 {1234}',
                        msg.as_bytes(),
                        b')',
                        b'1 OK UID FETCH completed'
                    ])

                    # Test download
                    params = DownloadAttachmentInput(uid="123", folder="INBOX", attachment_index=0)
                    result = await download_attachment(params)

                    # Verify response
                    assert result.uid == "123"
                    assert result.attachment_index == 0
                    assert result.filename == "test.pdf"
                    assert result.original_filename == "test.pdf"
                    assert result.content_type == "application/pdf"
                    assert result.size_bytes == len(pdf_data)
                    assert "attachments/email/downloads/123_0_test.pdf" in result.file_path

                    # Verify file was created
                    file_path = Path(temp_workspace) / result.file_path
                    assert file_path.exists()
                    assert file_path.read_bytes() == pdf_data


@pytest.mark.asyncio
async def test_download_attachment_not_found():
    """Test download with invalid attachment index."""
    with patch('imap.attachments.read_email') as mock_read:
        from imap.read import ReadEmailResponse, AttachmentInfo

        # Mock email with no attachments
        mock_read.return_value = ReadEmailResponse(
            uid="123",
            subject="No attachments",
            from_email="test@example.com",
            to=["recipient@example.com"],
            cc=[],
            date="2024-01-01T00:00:00",
            body_text="No attachments here",
            body_html="",
            attachments=[],
            in_reply_to=None,
            message_id="<123@example.com>"
        )

        with tempfile.TemporaryDirectory() as temp_workspace:
            with patch('imap.attachments.settings') as mock_settings:
                mock_settings.EMAIL_BASE_DIR = temp_workspace
                mock_settings.download_dir = Path(temp_workspace) / "attachments" / "email" / "downloads"

                params = DownloadAttachmentInput(uid="123", folder="INBOX", attachment_index=0)

                with pytest.raises(AttachmentNotFoundError):
                    await download_attachment(params)


@pytest.mark.asyncio
async def test_download_attachment_too_large():
    """Test download with oversized attachment."""
    with patch('imap.attachments.read_email') as mock_read:
        from imap.read import ReadEmailResponse, AttachmentInfo

        # Mock email with large attachment
        mock_read.return_value = ReadEmailResponse(
            uid="123",
            subject="Large attachment",
            from_email="test@example.com",
            to=["recipient@example.com"],
            cc=[],
            date="2024-01-01T00:00:00",
            body_text="Large attachment here",
            body_html="",
            attachments=[
                AttachmentInfo(
                    filename="large.pdf",
                    content_type="application/pdf",
                    size_bytes=200 * 1024 * 1024  # 200MB
                )
            ],
            in_reply_to=None,
            message_id="<123@example.com>"
        )

        with tempfile.TemporaryDirectory() as temp_workspace:
            with patch('imap.attachments.settings') as mock_settings:
                mock_settings.EMAIL_BASE_DIR = temp_workspace
                mock_settings.max_attachment_size_bytes = 100 * 1024 * 1024  # 100MB limit
                mock_settings.MAX_ATTACHMENT_SIZE_MB = 100
                mock_settings.download_dir = Path(temp_workspace) / "attachments" / "email" / "downloads"

                params = DownloadAttachmentInput(uid="123", folder="INBOX", attachment_index=0)

                with pytest.raises(AttachmentTooLargeError):
                    await download_attachment(params)


@pytest.mark.asyncio
async def test_download_attachment_sanitized_filename():
    """Test filename sanitization during download."""
    # Create mock email with attachment having dangerous filename
    msg = email.mime.multipart.MIMEMultipart()
    msg['Subject'] = 'Test with dangerous attachment'

    # Add text part
    text_part = email.mime.text.MIMEText('Email body')
    msg.attach(text_part)

    # Add attachment with dangerous filename
    pdf_data = b'%PDF-1.4 fake pdf content'
    attachment = email.mime.application.MIMEApplication(pdf_data, _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='../../../etc/passwd')
    msg.attach(attachment)

    with tempfile.TemporaryDirectory() as temp_workspace:
        with patch('imap.attachments.settings') as mock_settings:
            mock_settings.EMAIL_BASE_DIR = temp_workspace
            mock_settings.max_attachment_size_bytes = 100 * 1024 * 1024  # 100MB
            mock_settings.download_dir = Path(temp_workspace) / "attachments" / "email" / "downloads"

            with patch('imap.attachments.read_email') as mock_read_email:
                from imap.read import ReadEmailResponse, AttachmentInfo

                # Mock the read_email response with dangerous filename
                mock_read_email.return_value = ReadEmailResponse(
                    uid="123",
                    subject="Test with dangerous attachment",
                    from_email="sender@example.com",
                    to=["recipient@example.com"],
                    cc=[],
                    date="2024-01-01T00:00:00",
                    body_text="Email body",
                    body_html="",
                    attachments=[
                        AttachmentInfo(
                            filename="../../../etc/passwd",
                            content_type="application/octet-stream",
                            size_bytes=len(pdf_data)
                        )
                    ],
                    in_reply_to=None,
                    message_id="<123@example.com>"
                )

                with patch('imap.attachments.imap_pool') as mock_pool:
                    mock_client = AsyncMock()
                    mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

                    # Mock IMAP responses
                    mock_client.select.return_value = ("OK", [])
                    mock_client.uid.return_value = ("OK", [
                        b'1 FETCH (RFC822 {1234}',
                        msg.as_bytes(),
                        b')',
                        b'1 OK UID FETCH completed'
                    ])

                    # Test download
                    params = DownloadAttachmentInput(uid="123", folder="INBOX", attachment_index=0)
                    result = await download_attachment(params)

                    # Verify filename was sanitized
                    assert result.original_filename == "../../../etc/passwd"
                    assert result.filename == "___etc_passwd"  # Sanitized
                    assert "123_0____etc_passwd" in result.file_path

                    # Verify file was created safely in download directory
                    file_path = Path(temp_workspace) / result.file_path
                    assert file_path.exists()
                    assert file_path.read_bytes() == pdf_data
                    # Ensure it's within the downloads directory
                    assert "downloads" in str(file_path)


@pytest.mark.asyncio
async def test_download_attachment_filename_override():
    """Test download with custom filename override."""
    # Create mock email with attachment
    msg = email.mime.multipart.MIMEMultipart()
    msg['Subject'] = 'Test with attachment'

    # Add text part
    text_part = email.mime.text.MIMEText('Email body')
    msg.attach(text_part)

    # Add attachment
    pdf_data = b'%PDF-1.4 fake pdf content'
    attachment = email.mime.application.MIMEApplication(pdf_data, _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='original.pdf')
    msg.attach(attachment)

    with tempfile.TemporaryDirectory() as temp_workspace:
        with patch('imap.attachments.settings') as mock_settings:
            mock_settings.EMAIL_BASE_DIR = temp_workspace
            mock_settings.max_attachment_size_bytes = 100 * 1024 * 1024  # 100MB
            mock_settings.download_dir = Path(temp_workspace) / "attachments" / "email" / "downloads"

            with patch('imap.attachments.read_email') as mock_read_email:
                from imap.read import ReadEmailResponse, AttachmentInfo

                # Mock the read_email response
                mock_read_email.return_value = ReadEmailResponse(
                    uid="123",
                    subject="Test with attachment",
                    from_email="sender@example.com",
                    to=["recipient@example.com"],
                    cc=[],
                    date="2024-01-01T00:00:00",
                    body_text="Email body",
                    body_html="",
                    attachments=[
                        AttachmentInfo(
                            filename="original.pdf",
                            content_type="application/pdf",
                            size_bytes=len(pdf_data)
                        )
                    ],
                    in_reply_to=None,
                    message_id="<123@example.com>"
                )

                with patch('imap.attachments.imap_pool') as mock_pool:
                    mock_client = AsyncMock()
                    mock_pool.acquire_connection.return_value.__aenter__.return_value = mock_client

                    # Mock IMAP responses
                    mock_client.select.return_value = ("OK", [])
                    mock_client.uid.return_value = ("OK", [
                        b'1 FETCH (RFC822 {1234}',
                        msg.as_bytes(),
                        b')',
                        b'1 OK UID FETCH completed'
                    ])

                    # Test download with filename override
                    params = DownloadAttachmentInput(
                        uid="123",
                        folder="INBOX",
                        attachment_index=0,
                        filename_override="custom_name.pdf"
                    )
                    result = await download_attachment(params)

                    # Verify custom filename was used
                    assert result.original_filename == "original.pdf"
                    assert result.filename == "custom_name.pdf"
                    assert "123_0_custom_name.pdf" in result.file_path

                    # Verify file was created
                    file_path = Path(temp_workspace) / result.file_path
                    assert file_path.exists()
                    assert file_path.read_bytes() == pdf_data