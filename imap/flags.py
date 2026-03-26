"""IMAP flag operations: mark_email and move_email."""

import logging
import re
from typing import Optional
from pydantic import BaseModel, Field

from imap.client import imap_pool

logger = logging.getLogger(__name__)


class IMAPMessageNotFoundError(Exception):
    """Raised when IMAP message is not found."""
    pass


class IMAPFolderNotFoundError(Exception):
    """Raised when IMAP folder is not found."""
    pass


# Pydantic models for mark_email
class MarkEmailInput(BaseModel):
    """Input parameters for mark_email."""
    uid: str
    folder: str = Field(default="INBOX", description="Folder containing the message")
    read: Optional[bool] = Field(default=None, description="Set read status (adds/removes \\Seen)")
    flagged: Optional[bool] = Field(default=None, description="Set flagged status (adds/removes \\Flagged)")


class MarkEmailResponse(BaseModel):
    """Response from mark_email."""
    success: bool


async def mark_email(params: MarkEmailInput) -> MarkEmailResponse:
    """
    Set or clear flags on a message (read, flagged).

    Args:
        params: Mark email parameters

    Returns:
        MarkEmailResponse with success status

    Raises:
        IMAPMessageNotFoundError: If the message UID doesn't exist
    """
    async with imap_pool.acquire_connection() as client:
        # Select folder
        response = await client.select(params.folder)
        if response[0] != "OK":
            raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.folder}")

        # Apply read flag if specified
        if params.read is not None:
            if params.read:
                # Add \Seen flag
                response = await client.store(params.uid, "+FLAGS", "(\\Seen)", by_uid=True)
            else:
                # Remove \Seen flag
                response = await client.store(params.uid, "-FLAGS", "(\\Seen)", by_uid=True)

            if response[0] != "OK":
                raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Apply flagged flag if specified
        if params.flagged is not None:
            if params.flagged:
                # Add \Flagged flag
                response = await client.store(params.uid, "+FLAGS", "(\\Flagged)", by_uid=True)
            else:
                # Remove \Flagged flag
                response = await client.store(params.uid, "-FLAGS", "(\\Flagged)", by_uid=True)

            if response[0] != "OK":
                raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        return MarkEmailResponse(success=True)


# Pydantic models for move_email
class MoveEmailInput(BaseModel):
    """Input parameters for move_email."""
    uid: str
    from_folder: str = Field(default="INBOX", description="Source folder")
    to_folder: str = Field(..., description="Destination folder")


class MoveEmailResponse(BaseModel):
    """Response from move_email."""
    success: bool
    new_uid: Optional[str] = None


async def move_email(params: MoveEmailInput) -> MoveEmailResponse:
    """
    Move a message from one folder to another.

    Attempts RFC 6851 MOVE (atomic, preserves flags) first.  If the server
    does not advertise the MOVE capability, falls back to COPY + store
    \\Deleted + EXPUNGE.

    Args:
        params: Move email parameters

    Returns:
        MoveEmailResponse with success status and optional new_uid

    Raises:
        IMAPMessageNotFoundError: If the source message doesn't exist
        IMAPFolderNotFoundError: If the destination folder doesn't exist
    """
    async with imap_pool.acquire_connection() as client:
        # Select source folder
        response = await client.select(params.from_folder)
        if response[0] != "OK":
            raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.from_folder}")

        new_uid = None

        # Try RFC 6851 MOVE first (atomic, no expunge needed)
        try:
            response = await client.move(params.uid, params.to_folder, by_uid=True)

            if response[0] != "OK":
                error_msg = ""
                if response[1]:
                    first = response[1][0]
                    error_msg = (first.decode(errors="replace") if isinstance(first, bytes) else str(first))
                if "not found" in error_msg.lower() or "TRYCREATE" in error_msg:
                    raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.to_folder}")
                raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

            # Parse COPYUID / MOVEUID response for the new UID
            if response[1]:
                first = response[1][0]
                response_str = first.decode(errors="replace") if isinstance(first, bytes) else str(first)
                match = re.search(r'(?:COPY|MOVE)UID \d+ \d+ (\d+)', response_str)
                if match:
                    new_uid = match.group(1)

            return MoveEmailResponse(success=True, new_uid=new_uid)

        except Exception as e:
            # If MOVE capability is absent, aioimaplib raises Abort with
            # 'server has not MOVE capability'.  Fall through to COPY+DELETE.
            if "MOVE capability" not in str(e):
                raise

            logger.debug(f"Server lacks MOVE capability; falling back to COPY+DELETE for UID {params.uid}")

        # Fallback: COPY then mark deleted + expunge
        response = await client.copy(params.uid, params.to_folder, by_uid=True)

        if response[0] != "OK":
            error_msg = ""
            if response[1]:
                first = response[1][0]
                error_msg = (first.decode(errors="replace") if isinstance(first, bytes) else str(first))
            if "not found" in error_msg.lower() or "TRYCREATE" in error_msg:
                raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.to_folder}")
            raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Extract new UID from COPYUID response if available
        if response[1]:
            first = response[1][0]
            response_str = first.decode(errors="replace") if isinstance(first, bytes) else str(first)
            match = re.search(r'COPYUID \d+ \d+ (\d+)', response_str)
            if match:
                new_uid = match.group(1)

        # Mark source message as deleted
        response = await client.store(params.uid, "+FLAGS", "(\\Deleted)", by_uid=True)
        if response[0] != "OK":
            logger.warning(f"Failed to mark UID {params.uid} as deleted")

        # Expunge to permanently remove the deleted message
        response = await client.expunge()
        if response[0] != "OK":
            logger.warning(f"Failed to expunge folder {params.from_folder}")

        return MoveEmailResponse(success=True, new_uid=new_uid)
