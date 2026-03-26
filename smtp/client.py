"""SMTP client for sending emails."""

import logging
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Optional
from pydantic import BaseModel, Field
from aiosmtplib import SMTP
from config import settings

logger = logging.getLogger(__name__)


class SMTPAuthError(Exception):
    """Raised when SMTP authentication fails."""
    pass


class SMTPSendError(Exception):
    """Raised when SMTP send fails."""
    pass


def _smtp_starttls_connect_arg(starttls_setting: str) -> bool | None:
    """Map config value to aiosmtplib connect(start_tls=...) argument."""
    if starttls_setting == "none":
        return None
    if starttls_setting == "true":
        return True
    if starttls_setting == "false":
        return False
    raise ValueError('SMTP_STARTTLS must be one of: "none", "true", "false"')


async def send_message(msg: EmailMessage) -> str:
    """
    Send an email message via SMTP.

    Args:
        msg: EmailMessage to send

    Returns:
        message_id from the sent message

    Raises:
        SMTPAuthError: If authentication fails
        SMTPSendError: If sending fails
    """
    smtp = None
    try:
        # Create SMTP client
        smtp = SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            timeout=30,
        )

        # Connect, letting aiosmtplib handle STARTTLS mode during connect.
        await smtp.connect(
            start_tls=_smtp_starttls_connect_arg(settings.SMTP_STARTTLS)
        )

        # Authenticate
        try:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        except Exception as e:
            logger.error(f"SMTP authentication failed: {e}")
            raise SMTPAuthError(f"SMTP_AUTH_FAILED: {str(e)}")

        # Send message
        try:
            await smtp.send_message(msg)
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise SMTPSendError(f"SEND_FAILED: {str(e)}")

        # Get message ID
        message_id = msg.get("Message-ID", "")

        logger.debug(f"Email sent successfully: {message_id}")
        return message_id

    finally:
        # Close connection
        if smtp is not None:
            try:
                await smtp.quit()
            except Exception as e:
                logger.warning(f"Error closing SMTP connection: {e}")


# Pydantic models for send_email
class SendEmailInput(BaseModel):
    """Input parameters for send_email."""
    to: list[str] = Field(..., description="Recipient email addresses")
    cc: list[str] = Field(default_factory=list, description="CC recipients")
    bcc: list[str] = Field(default_factory=list, description="BCC recipients")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Plain text body")
    body_html: Optional[str] = Field(default=None, description="HTML body (optional)")
    from_name: Optional[str] = Field(default=None, description="Sender name (overrides DEFAULT_FROM_NAME)")


class SendEmailResponse(BaseModel):
    """Response from send_email."""
    success: bool
    message_id: str


async def send_email(params: SendEmailInput) -> SendEmailResponse:
    """
    Compose and send a new email via SMTP.

    Args:
        params: Send email parameters

    Returns:
        SendEmailResponse with success and message_id

    Raises:
        SMTPAuthError: If authentication fails
        SMTPSendError: If sending fails
    """
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

    # Generate Message-ID if not present
    if "Message-ID" not in msg:
        msg["Message-ID"] = make_msgid()

    # Set body
    if params.body_html:
        # Multipart message with text and HTML
        msg.set_content(params.body)
        msg.add_alternative(params.body_html, subtype="html")
    else:
        # Plain text only
        msg.set_content(params.body)

    # Send via SMTP
    message_id = await send_message(msg)

    return SendEmailResponse(success=True, message_id=message_id)


# Pydantic models for reply_email
class ReplyEmailInput(BaseModel):
    """Input parameters for reply_email."""
    uid: str = Field(..., description="UID of message to reply to")
    folder: str = Field(default="INBOX", description="Folder containing the original message")
    body: str = Field(..., description="Reply body (plain text)")
    body_html: Optional[str] = Field(default=None, description="Reply body (HTML)")
    reply_all: bool = Field(default=False, description="Reply to all recipients")


class ReplyEmailResponse(BaseModel):
    """Response from reply_email."""
    success: bool
    message_id: str


async def reply_email(params: ReplyEmailInput) -> ReplyEmailResponse:
    """
    Reply to an existing message, preserving thread headers.

    Args:
        params: Reply email parameters

    Returns:
        ReplyEmailResponse with success and message_id

    Raises:
        IMAPMessageNotFoundError: If original message not found
        SMTPAuthError: If authentication fails
        SMTPSendError: If sending fails
    """
    # Import here to avoid circular dependency
    from imap.read import read_email, ReadEmailInput

    # Fetch original message
    original = await read_email(ReadEmailInput(uid=params.uid, folder=params.folder))

    # Determine recipients
    if params.reply_all:
        # Reply to all: include original sender + original To (excluding self) + original Cc
        to_recipients = [original.from_email]

        # Add original To recipients (excluding self)
        for recipient in original.to:
            if settings.SMTP_USER not in recipient and recipient not in to_recipients:
                to_recipients.append(recipient)

        cc_recipients = original.cc.copy()
    else:
        # Reply to sender only
        to_recipients = [original.from_email]
        cc_recipients = []

    # Build subject with "Re: " prefix if not already present
    subject = original.subject
    if not subject.startswith("Re: "):
        subject = f"Re: {subject}"

    # Create reply message
    msg = EmailMessage()
    msg["From"] = settings.SMTP_USER
    msg["To"] = ", ".join(to_recipients)
    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)
    msg["Subject"] = subject

    # Set threading headers
    msg["In-Reply-To"] = original.message_id

    # Build References header
    references = []
    if original.in_reply_to:
        references.append(original.in_reply_to)
    if original.message_id:
        references.append(original.message_id)
    if references:
        msg["References"] = " ".join(references)

    # Generate Message-ID
    msg["Message-ID"] = make_msgid()

    # Set body
    if params.body_html:
        msg.set_content(params.body)
        msg.add_alternative(params.body_html, subtype="html")
    else:
        msg.set_content(params.body)

    # Send via SMTP
    message_id = await send_message(msg)

    return ReplyEmailResponse(success=True, message_id=message_id)
