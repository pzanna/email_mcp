"""
Email MCP Server - Main Application Entry Point

FastAPI application providing MCP-compliant email access via IMAP and SMTP.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from tools.mcp_routes import router as mcp_router

app = FastAPI(
    title="Email MCP Server",
    description="MCP server for email access via IMAP and SMTP",
    version="0.1.0",
)

# CORS middleware - allow all origins for MCP (can be restricted later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/mcp")
async def mcp_server_info():
    """MCP server discovery endpoint - public access for capability discovery."""
    return {
        "name": "email-mcp",
        "version": "0.1.0",
        "title": "Email MCP Server",
        "description": "MCP server for email access via IMAP and SMTP",
        "protocol": "MCP",
        "protocolVersion": "2025-03-26",
        "capabilities": {
            "tools": [
                "list_folders",
                "search_emails",
                "read_email",
                "mark_email",
                "move_email",
                "send_email",
                "reply_email"
            ],
            "logging": {},
            "features": [
                "IMAP email folder listing",
                "Email search with multiple criteria",
                "Full email content retrieval",
                "Email flag management (read/unread, flagged)",
                "Email folder operations (move)",
                "SMTP email sending",
                "Email reply with thread preservation"
            ]
        },
        "endpoints": {
            "main": "POST /mcp/call (MCP tool calls)",
            "info": "GET /mcp",
            "health": "GET /health",
            "tools": "GET /mcp/tools"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint - no authentication required."""
    return {"status": "ok", "server": settings.MCP_SERVER_NAME}


@app.get("/")
async def root():
    """Root endpoint - basic server info."""
    return {
        "server": settings.MCP_SERVER_NAME,
        "version": "0.1.0",
        "status": "running",
    }


# Include MCP router
app.include_router(mcp_router)
