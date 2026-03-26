#!/usr/bin/env python3
"""
Email MCP Server — stdio entry point for MCPB bundle.

Reads all credentials from environment variables (injected by Claude Desktop
from the OS keychain via manifest.json user_config).

The existing FastAPI app (main.py) is untouched; this file reuses the same
imap/ and smtp/ business logic via direct async calls.

Environment variables required:
    IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD, IMAP_SSL
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_STARTTLS
"""

import asyncio
import json
import logging
import os

# ---------------------------------------------------------------------------
# Ensure env vars have sensible defaults for optional settings BEFORE
# importing config (Settings() is instantiated at import time).
# ---------------------------------------------------------------------------
os.environ.setdefault("IMAP_SSL", "true")
os.environ.setdefault("SMTP_STARTTLS", "true")
# MCP_API_KEY is a required field in Settings() (used only by the HTTP server).
# In stdio mode it is never checked, but Settings() will fail to instantiate
# without it. This setdefault is load-bearing — do not remove it.
os.environ.setdefault("MCP_API_KEY", "unused-in-stdio-mode")
os.environ.setdefault("MCP_HOST", "127.0.0.1")
os.environ.setdefault("MCP_PORT", "8420")

# Now safe to import modules that reference config.settings at module scope.
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from config import settings  # noqa: E402  (after env defaults are set)
from imap.read import list_folders, read_email, ReadEmailInput
from imap.search import search_emails, SearchEmailsInput
from imap.flags import mark_email, move_email, MarkEmailInput, MoveEmailInput
from smtp.client import send_email, reply_email, SendEmailInput, ReplyEmailInput

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

server = Server("email-mcp")


# ---------------------------------------------------------------------------
# Tool listing
# ---------------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Return all 7 email tools."""
    return [
        types.Tool(
            name="list_folders",
            description="List all IMAP mailboxes/folders available on the account",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="search_emails",
            description="Search for emails using IMAP criteria. Returns message summaries (no body content).",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Folder to search in", "default": "INBOX"},
                    "from": {"type": "string", "description": "Filter by sender email address"},
                    "to": {"type": "string", "description": "Filter by recipient email address"},
                    "subject": {"type": "string", "description": "Filter by subject (substring match)"},
                    "since": {"type": "string", "description": "Filter messages since this date (ISO format YYYY-MM-DD)"},
                    "before": {"type": "string", "description": "Filter messages before this date (ISO format YYYY-MM-DD)"},
                    "unread": {"type": "boolean", "description": "Filter by unread status"},
                    "flagged": {"type": "boolean", "description": "Filter by flagged status"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20, max 50)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="read_email",
            description="Fetch the full content of a message by UID, including body and attachment metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "Message UID to fetch"},
                    "folder": {"type": "string", "description": "Folder containing the message", "default": "INBOX"},
                },
                "required": ["uid"],
            },
        ),
        types.Tool(
            name="mark_email",
            description="Set or clear flags on a message (read/unread, flagged/unflagged).",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "Message UID to mark"},
                    "folder": {"type": "string", "description": "Folder containing the message", "default": "INBOX"},
                    "read": {"type": "boolean", "description": "Set read status (adds/removes \\Seen flag)"},
                    "flagged": {"type": "boolean", "description": "Set flagged status (adds/removes \\Flagged flag)"},
                },
                "required": ["uid"],
            },
        ),
        types.Tool(
            name="move_email",
            description="Move a message from one folder to another.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "Message UID to move"},
                    "from_folder": {"type": "string", "description": "Source folder", "default": "INBOX"},
                    "to_folder": {"type": "string", "description": "Destination folder"},
                },
                "required": ["uid", "to_folder"],
            },
        ),
        types.Tool(
            name="send_email",
            description="Compose and send a new email via SMTP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients",
                        "default": [],
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC recipients",
                        "default": [],
                    },
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Plain text body"},
                    "body_html": {"type": "string", "description": "HTML body (optional, creates multipart if provided)"},
                    "from_name": {"type": "string", "description": "Sender name (overrides DEFAULT_FROM_NAME)"},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        types.Tool(
            name="reply_email",
            description="Reply to an existing message, preserving thread headers (In-Reply-To, References).",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "UID of message to reply to"},
                    "folder": {"type": "string", "description": "Folder containing the original message", "default": "INBOX"},
                    "body": {"type": "string", "description": "Reply body (plain text)"},
                    "body_html": {"type": "string", "description": "Reply body (HTML)"},
                    "reply_all": {"type": "boolean", "description": "Reply to all recipients (default: false)", "default": False},
                },
                "required": ["uid", "body"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    args = arguments or {}
    try:
        if name == "list_folders":
            result = await list_folders()

        elif name == "search_emails":
            # SearchEmailsInput uses alias "from" -> "from_email"
            result = await search_emails(SearchEmailsInput(**args))

        elif name == "read_email":
            result = await read_email(ReadEmailInput(**args))

        elif name == "mark_email":
            result = await mark_email(MarkEmailInput(**args))

        elif name == "move_email":
            result = await move_email(MoveEmailInput(**args))

        elif name == "send_email":
            result = await send_email(SendEmailInput(**args))

        elif name == "reply_email":
            result = await reply_email(ReplyEmailInput(**args))

        else:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "UnknownTool", "detail": f"No tool named '{name}'"}),
            )]

        return [types.TextContent(type="text", text=result.model_dump_json())]

    except Exception as exc:
        logger.error("Tool %s raised %s: %s", name, type(exc).__name__, exc)
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": type(exc).__name__, "detail": str(exc)}),
        )]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="email-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
