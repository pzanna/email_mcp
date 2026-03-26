# Email MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that provides email access via IMAP and SMTP. Enables AI agents and applications to read, search, send, and manage emails through a standardized HTTP/SSE interface.

## Features

- **7 Email Tools** via MCP:
  - `list_folders` - List all IMAP mailboxes/folders
  - `search_emails` - Search emails with filters (sender, subject, date range, read/flagged status)
  - `read_email` - Fetch full email content including body and attachment metadata
  - `mark_email` - Mark emails as read/unread or flagged/unflagged
  - `move_email` - Move emails between folders
  - `send_email` - Send new emails (plain text or multipart HTML)
  - `reply_email` - Reply to emails preserving thread headers

- **Production-Ready Architecture**:
  - Async-native IMAP/SMTP with connection pooling
  - Pydantic-based configuration and validation
  - Comprehensive error handling with structured exceptions
  - API key authentication via X-API-Key header
  - systemd service file for Ubuntu deployment

- **Test-Driven Development**:
  - 72 unit and integration tests
  - 100% coverage of core functionality
  - Mocked email servers for reproducible testing

## Requirements

- Python 3.13.5+ (tested with 3.13.5)
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

All 72 tests should pass.

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
MCP_BASE_URL=http://192.168.2.3:8420  # Your server IP
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

For remote server, use `http://192.168.2.3:8420/mcp` (replace with your server IP).

## Architecture

```
email_mcp/
├── main.py                 # FastAPI application entry point
├── config.py               # Pydantic settings (env vars)
├── auth.py                 # API key authentication middleware
├── imap/
│   ├── client.py          # IMAP connection pool
│   ├── read.py            # list_folders, read_email
│   ├── search.py          # search_emails
│   └── flags.py           # mark_email, move_email
├── smtp/
│   └── client.py          # send_email, reply_email
├── tools/
│   ├── definitions.py     # MCP tool schemas
│   └── mcp_routes.py      # MCP HTTP endpoints
└── tests/                  # 72 unit and integration tests
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
