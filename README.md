# Email MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that provides email access via IMAP and SMTP. Enables AI agents and applications to read, search, send, and manage emails through a standardized HTTP/SSE interface.

## Features

- **9 Email Tools** via MCP:
  - `list_folders` - List all IMAP mailboxes/folders
  - `search_emails` - Search emails with filters (sender, subject, date range, read/flagged status)
  - `read_email` - Fetch full email content including body and attachment metadata
  - `mark_email` - Mark emails as read/unread or flagged/unflagged
  - `move_email` - Move emails between folders
  - `send_email` - Send new emails (plain text or multipart HTML)
  - `reply_email` - Reply to emails preserving thread headers
  - `download_attachment` - Download email attachments to workspace directory
  - `send_email_with_attachments` - Send emails with file attachments from workspace

- **Production-Ready Architecture**:
  - Async-native IMAP/SMTP with connection pooling
  - Pydantic-based configuration and validation
  - Comprehensive error handling with structured exceptions
  - API key authentication via X-API-Key header
  - systemd service file for Ubuntu deployment

- **Test-Driven Development**:
  - 85+ unit and integration tests
  - 100% coverage of core functionality
  - Mocked email servers for reproducible testing

## Install with Claude Desktop (Recommended)

The easiest way to use this server is via the MCPB bundle — a single-file install
for [Claude Desktop](https://claude.ai/download).

### 1. Download

Download `email_mcp.mcpb` from the [latest release](../../releases/latest).

### 2. Install

Double-click `email_mcp.mcpb`. Claude Desktop will open an installation dialog.

### 3. Configure

Fill in your mail server credentials when prompted. All values are stored in the
OS keychain (macOS Keychain / Linux Secret Service):

| Field | Description | Example |
|-------|-------------|---------|
| **IMAP Host** | IMAP server hostname | `imap.gmail.com` |
| **IMAP Port** | IMAP server port | `993` (SSL) · `143` (STARTTLS) |
| **IMAP Username** | Your email address | `you@example.com` |
| **IMAP Password** | Password or app-specific password | `xxxx xxxx xxxx xxxx` |
| **IMAP SSL** | Use SSL/TLS for IMAP | `true` (port 993) · `false` (port 143) |
| **SMTP Host** | SMTP server hostname | `smtp.gmail.com` |
| **SMTP Port** | SMTP server port | `587` (STARTTLS) · `465` (SSL) |
| **SMTP Username** | Your email address | `you@example.com` |
| **SMTP Password** | Password or app-specific password | `xxxx xxxx xxxx xxxx` |
| **SMTP STARTTLS** | STARTTLS mode | `true` (port 587) · `false` · `none` (auto) |

> **Gmail users:** You must use an [App Password](https://support.google.com/accounts/answer/185833),
> not your regular Google account password. Enable IMAP under Gmail Settings →
> Forwarding and POP/IMAP.

### 4. Use

Once installed, Claude can access your email. Try:

> "List my unread emails from this week"
> "Search for emails from alice@example.com about the project"
> "Send an email to bob@example.com with subject 'Hello' and body 'Hi Bob!'"
> "Download the first attachment from email UID 12345"
> "Send an email with the report.pdf attachment to team@example.com"

---

## Requirements

- Python 3.10+ (3.13 recommended)
- IMAP and SMTP server access
- API key for MCP authentication

## Quick Start

### 1. Clone and Set Up

```bash
git clone https://github.com/pzanna/email_mcp.git
cd email_mcp
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

```bash
# IMAP Configuration
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=you@gmail.com
IMAP_PASSWORD=your-app-password
IMAP_SSL=true

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
# SMTP_STARTTLS mode: "none" (auto), "true" (force), "false" (disable)
SMTP_STARTTLS=true

# MCP Server Configuration
MCP_API_KEY=your-secret-api-key-here
MCP_HOST=127.0.0.1
MCP_PORT=8420
MCP_SERVER_NAME=email-mcp
MCP_BASE_URL=http://localhost:8420

# Optional
DEFAULT_FROM_NAME=Your Name
MAX_SEARCH_RESULTS=50
IMAP_POOL_SIZE=3

# Attachment Configuration
SAM_WORKSPACE_DIR=/path/to/workspace
MAX_ATTACHMENT_SIZE_MB=50
```

### 3. Run the Server

**Local development (Mac/Linux):**

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8420
```

**Access the server:**

- MCP endpoint: `http://localhost:8420/mcp`
- Health check: `http://localhost:8420/health`
- API docs: `http://localhost:8420/docs`

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_integration.py -v

# Run specific test
pytest tests/test_send.py::test_send_email_plain_text -v
```

All 85+ tests should pass.

## Usage Examples

### Authentication

All MCP endpoints require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-api-key-here" \
  http://localhost:8420/mcp/tools
```

### List Available Tools

```bash
curl -X GET http://localhost:8420/mcp/tools \
  -H "X-API-Key: your-secret-api-key-here"
```

### Search Emails

```bash
curl -X POST http://localhost:8420/mcp/call \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "search_emails",
      "arguments": {
        "from": "user@example.com",
        "subject": "invoice",
        "since": "2024-01-01",
        "limit": 10
      }
    }
  }'
```

### Send Email

```bash
curl -X POST http://localhost:8420/mcp/call \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "send_email",
      "arguments": {
        "to": ["recipient@example.com"],
        "subject": "Test Email",
        "body": "This is a test email.",
        "from_name": "My Name"
      }
    }
  }'
```

### Read Email

```bash
curl -X POST http://localhost:8420/mcp/call \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "read_email",
      "arguments": {
        "uid": "12345",
        "folder": "INBOX"
      }
    }
  }'
```

### Download Email Attachment

```bash
curl -X POST http://localhost:8420/mcp/call \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "download_attachment",
      "arguments": {
        "uid": "12345",
        "attachment_index": 0,
        "folder": "INBOX",
        "filename_override": "renamed_file.pdf"
      }
    }
  }'
```

Downloads the attachment to `SAM_WORKSPACE_DIR/attachments/email/downloads/` with security validation to ensure files stay within the workspace directory.

### Send Email with Attachments

```bash
curl -X POST http://localhost:8420/mcp/call \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "send_email_with_attachments",
      "arguments": {
        "to": ["recipient@example.com"],
        "cc": ["manager@example.com"],
        "subject": "Monthly Report",
        "body": "Please find the reports attached.",
        "body_html": "<p>Please find the <strong>reports</strong> attached.</p>",
        "from_name": "John Doe",
        "attachment_paths": [
          "attachments/email/uploads/report1.pdf",
          "attachments/email/uploads/report2.xlsx"
        ]
      }
    }
  }'
```

Attaches files from the workspace directory with full security validation and size limit enforcement.

## Attachment Handling

The email MCP server provides secure attachment handling with workspace-based file management.

### Workspace Directory Structure

All attachment operations are confined to the configured workspace directory:

```
SAM_WORKSPACE_DIR/
└── attachments/
    └── email/
        ├── downloads/    # Downloaded email attachments
        └── uploads/      # Files ready to attach to outgoing emails
```

### Security Features

- **Workspace Confinement**: All file operations are restricted to `SAM_WORKSPACE_DIR`
- **Path Traversal Protection**: Prevents access to files outside the workspace
- **Filename Sanitization**: Removes dangerous characters and handles reserved names
- **Size Limits**: Configurable per-file and total attachment size limits
- **File Type Validation**: Ensures attachment paths point to actual files

### Workflow Examples

**Download → Send Workflow**:
1. Use `download_attachment` to save email attachments to `downloads/`
2. Move or copy files to `uploads/` as needed
3. Use `send_email_with_attachments` to send files from `uploads/`

**Direct Upload Workflow**:
1. Place files in the `uploads/` directory
2. Use `send_email_with_attachments` with workspace-relative paths

### Configuration

```bash
# Workspace directory (required for attachment operations)
SAM_WORKSPACE_DIR=/path/to/your/workspace

# Maximum attachment size per file (default: 50MB)
MAX_ATTACHMENT_SIZE_MB=50
```

## Deployment

### Ubuntu Server with systemd

1. **Copy files to server:**

```bash
scp -r email_mcp user@server:/home/user/
```

1. **Set up Python environment:**

```bash
ssh user@server
cd ~/email_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. **Configure for remote access:**
Edit `.env`:

```bash
MCP_HOST=0.0.0.0  # Allow remote connections
MCP_BASE_URL=http://<your-server-ip>:8420  # Your server IP
```

1. **Install systemd service:**

```bash
# Edit email-mcp.service to match your paths
sudo cp email-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-mcp
sudo systemctl start email-mcp
```

1. **Check status:**

```bash
sudo systemctl status email-mcp
sudo journalctl -u email-mcp -f  # View logs
```

### Configure MCP Client

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "email": {
      "url": "http://localhost:8420/mcp",
      "headers": {
        "X-API-Key": "your-secret-api-key-here"
      }
    }
  }
}
```

For remote server, use `http://<your-server-ip>:8420/mcp` (replace with your server IP).

## Architecture

```
email_mcp/
├── main.py                 # FastAPI application entry point (HTTP/SSE mode)
├── mcp_server.py           # Stdio MCP entry point (MCPB / Claude Desktop mode)
├── config.py               # Pydantic settings (env vars)
├── auth.py                 # API key authentication middleware
├── imap/
│   ├── client.py          # IMAP connection pool
│   ├── read.py            # list_folders, read_email
│   ├── search.py          # search_emails
│   ├── flags.py           # mark_email, move_email
│   └── attachments.py     # download_attachment
├── smtp/
│   ├── client.py          # send_email, reply_email
│   └── attachments.py     # send_email_with_attachments
├── tools/
│   ├── definitions.py     # MCP tool schemas
│   ├── handlers.py        # Tool request routing
│   └── mcp_routes.py      # MCP HTTP endpoints
├── utils/
│   └── attachment_utils.py # Secure file handling utilities
└── tests/                  # 85+ unit and integration tests
```

### Key Design Patterns

- **Connection Pooling**: asyncio.Semaphore limits concurrent IMAP connections (default: 3)
- **Error Handling**: Structured exceptions map to MCP error responses
- **Email Threading**: In-Reply-To and References headers for reply chains
- **Multipart Messages**: Walk message tree to extract text/HTML/attachments
- **No Binary Transfer**: Attachments return metadata only (filename, size, content_type)

## Troubleshooting

### Gmail-Specific Setup

1. **Enable IMAP**: Settings → Forwarding and POP/IMAP → Enable IMAP
2. **App Password**: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password
3. **Gmail SMTP**: Use `smtp.gmail.com:587` with STARTTLS

### Connection Issues

```bash
# Test IMAP connection
openssl s_client -connect imap.gmail.com:993

# Test SMTP connection
openssl s_client -starttls smtp -connect smtp.gmail.com:587
```

### Common Errors

- **`CONNECTION_TIMEOUT`**: Check IMAP_HOST and IMAP_PORT
- **`AUTH_FAILED`**: Verify credentials, use App Password for Gmail
- **`FOLDER_NOT_FOUND`**: Folder names are case-sensitive (use `list_folders` to verify)
- **`MESSAGE_NOT_FOUND`**: UID may be invalid or message was deleted

**`SMTPException - Connection already using TLS`**: Set `SMTP_STARTTLS=none` in `.env` for auto mode. Valid values are `none`, `true`, and `false`.

## Development

### Project Structure

- `imap/` - IMAP client and tools (read, search, flags)
- `smtp/` - SMTP client and tools (send, reply)
- `tools/` - MCP endpoint handlers and schemas
- `tests/` - Unit and integration tests

### Running in Development

```bash
# Auto-reload on file changes
uvicorn main:app --reload --host 127.0.0.1 --port 8420

# Debug mode with verbose logging
LOG_LEVEL=DEBUG uvicorn main:app --host 127.0.0.1 --port 8420
```

### Adding New Tools

1. Define Pydantic models for input/output in appropriate module
2. Implement async function with error handling
3. Add tool schema to `tools/definitions.py`
4. Wire dispatcher in `tools/mcp_routes.py`
5. Write tests following TDD approach

## License

MIT

## Contributing

Contributions are welcome! Please:

1. Write tests for all new features
2. Follow existing code style (black, isort, mypy)
3. Update this README for significant changes
4. Ensure all tests pass before submitting PRs

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
