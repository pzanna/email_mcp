"""MCP tool schema definitions."""

# MCP tool schemas following the Model Context Protocol specification
# Reference: https://modelcontextprotocol.io/docs/concepts/tools

TOOL_SCHEMAS = [
    {
        "name": "list_folders",
        "description": "List all IMAP mailboxes/folders available on the account",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "search_emails",
        "description": "Search for emails using IMAP criteria. Returns message summaries (no body content).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "Folder to search in",
                    "default": "INBOX"
                },
                "from": {
                    "type": "string",
                    "description": "Filter by sender email address"
                },
                "to": {
                    "type": "string",
                    "description": "Filter by recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Filter by subject (substring match)"
                },
                "since": {
                    "type": "string",
                    "description": "Filter messages since this date (ISO format YYYY-MM-DD)"
                },
                "before": {
                    "type": "string",
                    "description": "Filter messages before this date (ISO format YYYY-MM-DD)"
                },
                "unread": {
                    "type": "boolean",
                    "description": "Filter by unread status"
                },
                "flagged": {
                    "type": "boolean",
                    "description": "Filter by flagged status"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20, max 50)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "read_email",
        "description": "Fetch the full content of a message by UID, including body and attachment metadata (no binary transfer).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "Message UID to fetch"
                },
                "folder": {
                    "type": "string",
                    "description": "Folder containing the message",
                    "default": "INBOX"
                }
            },
            "required": ["uid"]
        }
    },
    {
        "name": "mark_email",
        "description": "Set or clear flags on a message (read/unread, flagged/unflagged).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "Message UID to mark"
                },
                "folder": {
                    "type": "string",
                    "description": "Folder containing the message",
                    "default": "INBOX"
                },
                "read": {
                    "type": "boolean",
                    "description": "Set read status (adds/removes \\Seen flag)"
                },
                "flagged": {
                    "type": "boolean",
                    "description": "Set flagged status (adds/removes \\Flagged flag)"
                }
            },
            "required": ["uid"]
        }
    },
    {
        "name": "move_email",
        "description": "Move a message from one folder to another.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "Message UID to move"
                },
                "from_folder": {
                    "type": "string",
                    "description": "Source folder",
                    "default": "INBOX"
                },
                "to_folder": {
                    "type": "string",
                    "description": "Destination folder"
                }
            },
            "required": ["uid", "to_folder"]
        }
    },
    {
        "name": "send_email",
        "description": "Compose and send a new email via SMTP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipient email addresses"
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CC recipients",
                    "default": []
                },
                "bcc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "BCC recipients",
                    "default": []
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Plain text body"
                },
                "body_html": {
                    "type": "string",
                    "description": "HTML body (optional, creates multipart if provided)"
                },
                "from_name": {
                    "type": "string",
                    "description": "Sender name (overrides DEFAULT_FROM_NAME)"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "reply_email",
        "description": "Reply to an existing message, preserving thread headers (In-Reply-To, References).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "UID of message to reply to"
                },
                "folder": {
                    "type": "string",
                    "description": "Folder containing the original message",
                    "default": "INBOX"
                },
                "body": {
                    "type": "string",
                    "description": "Reply body (plain text)"
                },
                "body_html": {
                    "type": "string",
                    "description": "Reply body (HTML)"
                },
                "reply_all": {
                    "type": "boolean",
                    "description": "Reply to all recipients (default: false)",
                    "default": False
                }
            },
            "required": ["uid", "body"]
        }
    }
]
