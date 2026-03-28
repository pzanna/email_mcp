"""IMAP attachment download functionality."""

import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from email import message_from_bytes

from config import settings
from imap.client import imap_pool
from imap.read import read_email, ReadEmailInput, IMAPMessageNotFoundError
from utils.attachment_utils import sanitize_filename, ensure_directory_exists, get_mime_type_from_filename
from tools.mcp_routes import AttachmentNotFoundError, AttachmentTooLargeError

logger = logging.getLogger(__name__)


class DownloadAttachmentInput(BaseModel):
    """Input parameters for download_attachment."""
    uid: str = Field(..., description="UID of email containing attachment")
    folder: str = Field(default="INBOX", description="Folder containing the email")
    attachment_index: int = Field(..., description="Zero-based index of attachment to download")
    filename_override: Optional[str] = Field(default=None, description="Override filename (sanitized)")


class DownloadAttachmentResponse(BaseModel):
    """Response from download_attachment tool."""
    file_path: str = Field(..., description="Workspace-relative path to downloaded file")
    absolute_path: str = Field(..., description="Absolute filesystem path")
    filename: str = Field(..., description="Sanitized filename")
    original_filename: str = Field(..., description="Original attachment filename")
    content_type: str = Field(..., description="MIME content type")
    size_bytes: int = Field(..., description="File size in bytes")
    attachment_index: int = Field(..., description="Attachment index from email")
    uid: str = Field(..., description="Email UID")


async def download_attachment(params: DownloadAttachmentInput) -> DownloadAttachmentResponse:
    """
    Download an email attachment to the workspace directory.

    Args:
        params: Download parameters

    Returns:
        DownloadAttachmentResponse with file paths and metadata

    Raises:
        AttachmentNotFoundError: If attachment index is invalid
        AttachmentTooLargeError: If attachment exceeds size limit
        IMAPMessageNotFoundError: If email not found
    """
    # First get email metadata to check if attachment exists
    try:
        email_data = await read_email(ReadEmailInput(uid=params.uid, folder=params.folder))
    except IMAPMessageNotFoundError:
        raise AttachmentNotFoundError(f"EMAIL_NOT_FOUND: UID {params.uid}")

    if params.attachment_index >= len(email_data.attachments):
        raise AttachmentNotFoundError(
            f"Attachment index {params.attachment_index} not found. Email has {len(email_data.attachments)} attachments."
        )

    attachment_info = email_data.attachments[params.attachment_index]

    # Check size limit
    if attachment_info.size_bytes > settings.max_attachment_size_bytes:
        size_mb = attachment_info.size_bytes / (1024 * 1024)
        raise AttachmentTooLargeError(
            f"Attachment size {size_mb:.1f}MB exceeds limit of {settings.MAX_ATTACHMENT_SIZE_MB}MB"
        )

    # Now fetch the full email to get attachment content
    async with imap_pool.acquire_connection() as client:
        # Select folder
        response = await client.select(params.folder)
        if response[0] != "OK":
            raise AttachmentNotFoundError(f"FOLDER_NOT_FOUND: {params.folder}")

        # Fetch full message
        response = await client.uid('FETCH', params.uid, "(RFC822)")
        if response[0] != "OK":
            raise AttachmentNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Parse response - following the same pattern as read_email
        raw_data = response[1]
        if not raw_data or len(raw_data) < 2:
            raise AttachmentNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        email_bytes = raw_data[1]  # bytearray literal content

        if not email_bytes:
            raise AttachmentNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Parse email
        msg = message_from_bytes(email_bytes)

        # Extract attachment content
        attachment_content = None
        current_attachment_index = 0

        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")

            if "attachment" in content_disposition:
                if current_attachment_index == params.attachment_index:
                    attachment_content = part.get_payload(decode=True)
                    break
                current_attachment_index += 1

        if attachment_content is None:
            raise AttachmentNotFoundError(f"Could not extract attachment content at index {params.attachment_index}")

    # Prepare filename
    original_filename = attachment_info.filename
    if params.filename_override:
        filename = sanitize_filename(params.filename_override)
    else:
        filename = sanitize_filename(original_filename)

    # Create unique filename with UID and index
    unique_filename = f"{params.uid}_{params.attachment_index}_{filename}"

    # Ensure download directory exists
    ensure_directory_exists(settings.download_dir)

    # Write file to download directory
    file_path = settings.download_dir / unique_filename
    file_path.write_bytes(attachment_content)

    # Create workspace-relative path
    workspace_relative_path = str(file_path.relative_to(Path(settings.SAM_WORKSPACE_DIR)))

    logger.info(f"Downloaded attachment: {unique_filename} ({len(attachment_content)} bytes)")

    return DownloadAttachmentResponse(
        file_path=workspace_relative_path,
        absolute_path=str(file_path),
        filename=filename,
        original_filename=original_filename,
        content_type=attachment_info.content_type,
        size_bytes=len(attachment_content),
        attachment_index=params.attachment_index,
        uid=params.uid
    )