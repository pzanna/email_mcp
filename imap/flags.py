"""IMAP flag operations: mark_email and move_email."""

import logging
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
                response = await client.store(params.uid, "+FLAGS", "(\\Seen)")
            else:
                # Remove \Seen flag
                response = await client.store(params.uid, "-FLAGS", "(\\Seen)")

            if response[0] != "OK":
                raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Apply flagged flag if specified
        if params.flagged is not None:
            if params.flagged:
                # Add \Flagged flag
                response = await client.store(params.uid, "+FLAGS", "(\\Flagged)")
            else:
                # Remove \Flagged flag
                response = await client.store(params.uid, "-FLAGS", "(\\Flagged)")

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

        # Copy message to destination folder
        response = await client.copy(params.uid, params.to_folder)

        if response[0] != "OK":
            error_msg = response[1][0].decode() if response[1] else ""
            if "not found" in error_msg.lower() or "TRYCREATE" in error_msg:
                raise IMAPFolderNotFoundError(f"FOLDER_NOT_FOUND: {params.to_folder}")
            else:
                raise IMAPMessageNotFoundError(f"MESSAGE_NOT_FOUND: UID {params.uid}")

        # Extract new UID if available (from COPYUID response)
        new_uid = None
        if response[1]:
            response_str = response[1][0].decode() if isinstance(response[1][0], bytes) else str(response[1][0])
            # Parse COPYUID response: [COPYUID uidvalidity src_uid dest_uid]
            import re
            match = re.search(r'COPYUID \d+ \d+ (\d+)', response_str)
            if match:
                new_uid = match.group(1)

        # Mark source message as deleted
        response = await client.store(params.uid, "+FLAGS", "(\\Deleted)")
        if response[0] != "OK":
            logger.warning(f"Failed to mark UID {params.uid} as deleted")

        # Expunge to permanently delete
        response = await client.expunge()
        if response[0] != "OK":
            logger.warning(f"Failed to expunge folder {params.from_folder}")

        return MoveEmailResponse(success=True, new_uid=new_uid)
