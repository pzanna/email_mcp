"""SMTP attachment handling for sending emails with file attachments."""

import logging
from pathlib import Path
from typing import List
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from pydantic import BaseModel, Field

from utils.attachment_utils import validate_workspace_path, get_mime_type_from_filename, format_file_size
from smtp.client import send_message, _save_to_sent
from config import settings
from tools.mcp_routes import InvalidAttachmentPathError, AttachmentTooLargeError

logger = logging.getLogger(__name__)


class AttachmentInfo(BaseModel):
    """Information about an attachment to be sent."""
    file_path: str = Field(..., description="Path to attachment file (workspace-relative or absolute)")
    filename: str = Field(..., description="Final filename used in email")
    content_type: str = Field(..., description="MIME content type")
    size_bytes: int = Field(..., description="File size in bytes")


class SendEmailWithAttachmentsInput(BaseModel):
    """Input parameters for send_email_with_attachments."""
    to: List[str] = Field(..., description="Recipient email addresses")
    cc: List[str] = Field(default_factory=list, description="CC recipients")
    bcc: List[str] = Field(default_factory=list, description="BCC recipients")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Plain text body")
    body_html: str = Field(None, description="HTML body (optional)")
    from_name: str = Field(None, description="Sender name (overrides DEFAULT_FROM_NAME)")
    attachment_paths: List[str] = Field(..., description="Paths to files to attach (workspace-relative or absolute)")


class SendEmailWithAttachmentsResponse(BaseModel):
    """Response from send_email_with_attachments."""
    success: bool
    message_id: str
    attachments: List[AttachmentInfo] = Field(..., description="Metadata for attached files")


async def send_email_with_attachments(params: SendEmailWithAttachmentsInput) -> SendEmailWithAttachmentsResponse:
    """
    Compose and send an email with file attachments via SMTP.

    Args:
        params: Send email with attachments parameters

    Returns:
        SendEmailWithAttachmentsResponse with success, message_id, and attachment metadata

    Raises:
        InvalidAttachmentPathError: If any attachment path is outside workspace
        AttachmentTooLargeError: If any attachment is too large
        FileNotFoundError: If any attachment file is missing
        SMTPAuthError: If authentication fails
        SMTPSendError: If sending fails
    """
    # Validate and collect attachment information
    attachments_info = []
    total_size = 0

    for attachment_path in params.attachment_paths:
        # Validate path is within workspace
        validated_path = validate_workspace_path(attachment_path, settings.SAM_WORKSPACE_DIR)

        # Check file exists
        if not validated_path.exists():
            raise FileNotFoundError(f"Attachment file not found: {attachment_path}")

        if not validated_path.is_file():
            raise InvalidAttachmentPathError(f"Attachment path is not a file: {attachment_path}")

        # Get file info
        size_bytes = validated_path.stat().st_size
        filename = validated_path.name
        content_type = get_mime_type_from_filename(filename)

        # Check size limits
        if size_bytes > settings.max_attachment_size_bytes:
            size_str = format_file_size(size_bytes)
            limit_str = format_file_size(settings.max_attachment_size_bytes)
            raise AttachmentTooLargeError(
                f"Attachment '{filename}' ({size_str}) exceeds limit of {limit_str}"
            )

        total_size += size_bytes

        # Check total attachment size (reasonable limit for most email servers)
        max_total_size = settings.max_attachment_size_bytes * 2  # Allow up to 2x per-file limit for total
        if total_size > max_total_size:
            total_str = format_file_size(total_size)
            limit_str = format_file_size(max_total_size)
            raise AttachmentTooLargeError(
                f"Total attachments size ({total_str}) exceeds limit of {limit_str}"
            )

        attachments_info.append(AttachmentInfo(
            file_path=str(validated_path.relative_to(Path(settings.SAM_WORKSPACE_DIR))),
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes
        ))

    # Create email message
    msg = EmailMessage()

    # Determine from name
    from_name = params.from_name if params.from_name else settings.DEFAULT_FROM_NAME

    # Set headers
    msg["From"] = f"{from_name} <{settings.SMTP_USER}>" if from_name else settings.SMTP_USER
    msg["To"] = ", ".join(params.to)
    if params.cc:
        msg["Cc"] = ", ".join(params.cc)
    if params.bcc:
        msg["Bcc"] = ", ".join(params.bcc)
    msg["Subject"] = params.subject

    # Generate Message-ID and set Date if not present
    if "Message-ID" not in msg:
        msg["Message-ID"] = make_msgid()
    if "Date" not in msg:
        msg["Date"] = formatdate(localtime=True)

    # Set body content
    if params.body_html:
        # Multipart message with text and HTML
        msg.set_content(params.body)
        msg.add_alternative(params.body_html, subtype="html")
    else:
        # Plain text only
        msg.set_content(params.body)

    # Add attachments
    for attachment_info in attachments_info:
        attachment_path = Path(settings.SAM_WORKSPACE_DIR) / attachment_info.file_path

        # Read file content
        with open(attachment_path, 'rb') as f:
            file_data = f.read()

        # Add attachment to message
        maintype, subtype = attachment_info.content_type.split('/', 1)
        msg.add_attachment(
            file_data,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_info.filename
        )

        logger.debug(f"Added attachment: {attachment_info.filename} ({format_file_size(attachment_info.size_bytes)})")

    # Send via SMTP
    message_id = await send_message(msg)

    # Save a copy to the Sent folder on the IMAP server (non-fatal)
    try:
        await _save_to_sent(msg)
    except Exception as e:
        logger.warning(f"Could not save outgoing message to Sent folder: {e}")

    logger.info(f"Email sent with {len(attachments_info)} attachments: {message_id}")

    return SendEmailWithAttachmentsResponse(
        success=True,
        message_id=message_id,
        attachments=attachments_info
    )