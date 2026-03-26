"""IMAP read operations: list_folders and read_email."""

import re
import logging
from email import message_from_bytes
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from imap.client import imap_pool

logger = logging.getLogger(__name__)


def _parse_date(raw: str) -> str:
    """
    Parse a raw RFC 2822 Date header value into an ISO 8601 string.

    Returns empty string on any parse failure or missing header.
    """
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        return ""


class IMAPMessageNotFoundError(Exception):
    """Raised when IMAP message is not found."""
    pass


# Pydantic models for list_folders
class FolderInfo(BaseModel):
    """Information about an IMAP folder."""
    name: str
    delimiter: str
    flags: list[str]


class ListFoldersResponse(BaseModel):
    """Response from list_folders tool."""
    folders: list[FolderInfo]


async def list_folders() -> ListFoldersResponse:
    """
    List all IMAP mailboxes/folders available on the account.

    Returns:
        ListFoldersResponse with list of folders

    Raises:
        IMAPConnectionError: If connection to IMAP server fails
        IMAPAuthError: If authentication fails
    """
    async with imap_pool.acquire_connection() as client:
        # Get folder list — aioimaplib requires both positional args
        response = await client.list('""', "*")

        if response[0] != "OK":
            logger.error(f"LIST command failed: {response}")
            return ListFoldersResponse(folders=[])

        folders = []

        # Parse each folder line
        # Format: (flags) "delimiter" "name"
        # Example: (\HasNoChildren) "/" "INBOX"
        for line in response[1]:
            if not line:
                continue

            # Decode bytes to string
            line_str = line.decode() if isinstance(line, bytes) else line

            # Parse using regex
            # Match: (flags) "delimiter" "name" or (\flags) delimiter name
            match = re.match(r'\(([^)]*)\)\s+"?([^"]+)"?\s+"?([^"]+)"?', line_str)
            if not match:
                logger.warning(f"Could not parse folder line: {line_str}")
                continue

            flags_str, delimiter, name = match.groups()

            # Parse flags - split by space and filter empty strings
            flags = [f.strip() for f in flags_str.split() if f.strip()]

            # Remove quotes from delimiter and name if present
            delimiter = delimiter.strip('"')
            name = name.strip('"')

            folders.append(FolderInfo(
                name=name,
                delimiter=delimiter,
                flags=flags,
            ))

        logger.debug(f"Listed {len(folders)} folders")
        return ListFoldersResponse(folders=folders)


# Pydantic models for read_email
class ReadEmailInput(BaseModel):
    """Input parameters for read_email."""
    uid: str
    folder: str = Field(default="INBOX", description="Folder containing the message")


class AttachmentInfo(BaseModel):
    """Metadata about an email attachment."""
    filename: str
    content_type: str
    size_bytes: int


class ReadEmailResponse(BaseModel):
    """Response from read_email tool."""
    uid: str
    subject: str
    from_email: str = Field(alias="from")
    to: list[str]
    cc: list[str]
    date: str
    body_text: str
    body_html: str
    attachments: list[AttachmentInfo]
    in_reply_to: Optional[str] = None
    message_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


async def read_email(params: ReadEmailInput) -> ReadEmailResponse:
    """
    Fetch the full content of a message by UID.

    Args:
        params: Read email parameters (uid, folder)

    Returns:
        ReadEmailResponse with full message content

    Raises:
        IMAPMessageNotFoundError: If the message UID doesn't exist
    """
    async with imap_pool.acquire_connection() as client:
        # Select folder
        response = await client.select(params.folder)
        if response[0] != "OK":
            raise IMAPMessageNotFoundError(f"FOLDER_NOT_FOUND: {params.folder}")

        # Fetch full message via UID FETCH for stable addressing
        response = await client.uid('FETCH', params.uid, "(RFC822)")

        if response[0] != "OK":
            raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Parse response
        # aioimaplib response[1] is a flat list:
        #   [0] bytes     — metadata: "N FETCH (RFC822 {size}"
        #   [1] bytearray — literal content (the full RFC822 message)
        #   [2] bytes     — closing b')'
        #   [3] bytes     — tagged OK line
        raw_data = response[1]
        if not raw_data or len(raw_data) < 2:
            raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        email_bytes = raw_data[1]   # bytearray literal content

        if not email_bytes:
            raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Parse email
        msg = message_from_bytes(email_bytes)

        # Extract basic headers
        subject = msg.get("Subject", "")
        from_email = msg.get("From", "")
        to_str = msg.get("To", "")
        cc_str = msg.get("Cc", "")
        date = _parse_date(msg.get("Date") or msg.get("date") or "")
        message_id = msg.get("Message-ID")
        in_reply_to = msg.get("In-Reply-To")

        # Parse To and Cc lists
        to_list = [addr.strip() for addr in to_str.split(",") if addr.strip()]
        cc_list = [addr.strip() for addr in cc_str.split(",") if addr.strip()]

        # Extract body parts
        body_text = ""
        body_html = ""
        attachments = []

        if msg.is_multipart():
            # Multipart message - extract parts
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get("Content-Disposition", "")

                # Check if it's an attachment
                if "attachment" in content_disposition:
                    filename = part.get_filename() or "unnamed"
                    payload = part.get_payload(decode=True)
                    size_bytes = len(payload) if payload else 0

                    attachments.append(AttachmentInfo(
                        filename=filename,
                        content_type=content_type,
                        size_bytes=size_bytes,
                    ))

                # Extract text parts
                elif content_type == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(errors="ignore")

                elif content_type == "text/html" and not body_html:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode(errors="ignore")

        else:
            # Single part message
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)

            if payload:
                decoded = payload.decode(errors="ignore")
                if content_type == "text/html":
                    body_html = decoded
                else:
                    body_text = decoded

        return ReadEmailResponse(
            uid=params.uid,
            subject=subject,
            from_email=from_email,
            to=to_list,
            cc=cc_list,
            date=date,
            body_text=body_text,
            body_html=body_html or "",
            attachments=attachments,
            in_reply_to=in_reply_to,
            message_id=message_id,
        )
