"""IMAP search operations."""

import logging
import re
from datetime import datetime
from email import message_from_bytes
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from imap.client import imap_pool

logger = logging.getLogger(__name__)


class IMAPFolderNotFoundError(Exception):
    """Raised when IMAP folder is not found."""
    pass


# Pydantic models
class SearchEmailsInput(BaseModel):
    """Input parameters for search_emails."""
    folder: str = Field(default="INBOX", description="Folder to search in")
    from_email: Optional[str] = Field(default=None, alias="from", description="Filter by sender email")
    to: Optional[str] = Field(default=None, description="Filter by recipient email")
    subject: Optional[str] = Field(default=None, description="Filter by subject (substring match)")
    since: Optional[str] = Field(default=None, description="Filter messages since this date (ISO format YYYY-MM-DD)")
    before: Optional[str] = Field(default=None, description="Filter messages before this date (ISO format YYYY-MM-DD)")
    unread: Optional[bool] = Field(default=None, description="Filter by unread status")
    flagged: Optional[bool] = Field(default=None, description="Filter by flagged status")
    limit: int = Field(default=20, description="Maximum number of results (max 50)")

    model_config = ConfigDict(populate_by_name=True)  # Allow both 'from' and 'from_email'


class MessageSummary(BaseModel):
    """Summary of an email message."""
    uid: str
    subject: str
    from_email: str = Field(alias="from")
    to: list[str]
    date: str
    unread: bool
    flagged: bool
    has_attachments: bool

    model_config = ConfigDict(populate_by_name=True)


class SearchEmailsResponse(BaseModel):
    """Response from search_emails."""
    total: int
    messages: list[MessageSummary]


async def search_emails(params: SearchEmailsInput) -> SearchEmailsResponse:
    """
    Search for emails using IMAP criteria.

    Args:
        params: Search parameters

    Returns:
        SearchEmailsResponse with matching message summaries

    Raises:
        IMAPFolderNotFoundError: If the specified folder doesn't exist
    """
    # Enforce max limit
    limit = min(params.limit, 50)

    async with imap_pool.acquire_connection() as client:
        # Select folder
        response = await client.select(params.folder)
        if response[0] != "OK":
            raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.folder}")

        # Build search criteria
        criteria = []

        if params.from_email:
            criteria.append(f'FROM "{params.from_email}"')

        if params.to:
            criteria.append(f'TO "{params.to}"')

        if params.subject:
            criteria.append(f'SUBJECT "{params.subject}"')

        if params.since:
            # Convert ISO date to IMAP date format (DD-Mon-YYYY)
            dt = datetime.fromisoformat(params.since)
            imap_date = dt.strftime("%d-%b-%Y")
            criteria.append(f'SINCE {imap_date}')

        if params.before:
            dt = datetime.fromisoformat(params.before)
            imap_date = dt.strftime("%d-%b-%Y")
            criteria.append(f'BEFORE {imap_date}')

        if params.unread is not None:
            if params.unread:
                criteria.append('UNSEEN')
            else:
                criteria.append('SEEN')

        if params.flagged is not None:
            if params.flagged:
                criteria.append('FLAGGED')
            else:
                criteria.append('UNFLAGGED')

        # Default to ALL if no criteria
        if not criteria:
            search_str = 'ALL'
        else:
            search_str = ' '.join(criteria)

        # Execute UID SEARCH for stable addressing
        response = await client.uid_search(search_str)

        if response[0] != "OK":
            logger.error(f"SEARCH failed: {response}")
            return SearchEmailsResponse(total=0, messages=[])

        # Parse UIDs
        uid_data = response[1][0] if response[1] else b""
        if not uid_data:
            return SearchEmailsResponse(total=0, messages=[])

        uids = uid_data.decode().split()
        total = len(uids)

        # Apply limit — most-recent messages are last; reverse so newest come first
        uids = uids[-limit:][::-1]

        # Fetch message summaries
        messages = []
        for uid in uids:
            try:
                # Fetch headers and flags for this message via UID FETCH
                fetch_response = await client.uid('FETCH', uid, '(FLAGS RFC822.HEADER)')

                if fetch_response[0] != "OK":
                    logger.warning(f"Failed to fetch UID {uid}")
                    continue

                # aioimaplib response[1] is a flat list:
                #   [0] bytes     — metadata: "N FETCH (FLAGS (...) RFC822.HEADER {size}"
                #   [1] bytearray — literal content (the header bytes)
                #   [2] bytes     — closing b')'
                #   [3] bytes     — tagged OK line
                raw_data = fetch_response[1]

                if not raw_data or len(raw_data) < 2:
                    continue

                metadata_bytes = raw_data[0]
                headers_bytes = raw_data[1]   # bytearray literal content

                if not headers_bytes:
                    continue

                # Parse email headers
                msg = message_from_bytes(headers_bytes)

                # Extract flags from the metadata line
                flags_line = metadata_bytes.decode(errors="replace") if isinstance(metadata_bytes, bytes) else str(metadata_bytes)
                flags = []
                if "FLAGS" in flags_line:
                    flags_match = re.search(r'FLAGS \(([^)]*)\)', flags_line)
                    if flags_match:
                        flags = flags_match.group(1).split()

                # Build summary
                from_email = msg.get("From", "")
                to_str = msg.get("To", "")
                to_list = [addr.strip() for addr in to_str.split(",") if addr.strip()]
                has_attachments = "attachment" in msg.get("Content-Disposition", "").lower()

                summary = MessageSummary(
                    uid=uid,
                    subject=msg.get("Subject", ""),
                    from_email=from_email,
                    to=to_list,
                    date=msg.get("Date", ""),
                    unread="\\Seen" not in flags,
                    flagged="\\Flagged" in flags,
                    has_attachments=has_attachments,
                )

                messages.append(summary)

            except Exception as e:
                logger.error(f"Error parsing message UID {uid}: {e}")
                continue

        return SearchEmailsResponse(total=total, messages=messages)
