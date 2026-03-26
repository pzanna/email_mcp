"""
Email MCP Server - Main Application Entry Point

FastAPI application providing MCP-compliant email access via IMAP and SMTP.
"""

from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from tools.mcp_routes import router as mcp_router, MCPToolCallRequest, MCPToolCallResponse
from auth import verify_api_key
from typing import Union, Any
from pydantic import BaseModel

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


class MCPInitializeResponse(BaseModel):
    """MCP initialize response format."""
    protocolVersion: str
    capabilities: dict[str, Any]
    serverInfo: dict[str, str]


# Union type to handle different MCP response types
MCPResponse = Union[MCPInitializeResponse, MCPToolCallResponse]


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
            "main": "POST /mcp (JSON-RPC 2.0)",
            "info": "GET /mcp",
            "health": "GET /health",
            "tools": "GET /mcp/tools"
        }
    }


@app.post("/mcp")
async def mcp_tool_call(request: MCPToolCallRequest, api_key: str = Depends(verify_api_key)) -> MCPResponse:
    """MCP endpoint - handles JSON-RPC 2.0 initialize and tool calls with authentication."""
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Received MCP request: method='{request.method}', params={request.params}")

    if request.method == "initialize":
        # Handle MCP initialization handshake
        logger.info("Handling MCP initialize request")
        return MCPInitializeResponse(
            protocolVersion="2025-03-26",
            capabilities={
                "tools": {
                    "listChanged": False
                },
                "logging": {},
            },
            serverInfo={
                "name": "email-mcp",
                "version": "0.1.0"
            }
        )

    elif request.method == "tools/call":
        # Handle tool execution
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if not tool_name:
            logger.error(f"Missing tool name in params: {request.params}")
            raise HTTPException(status_code=400, detail="Missing tool name")

        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

        # Import here to avoid circular imports
        from tools.handlers import execute_tool
        return await execute_tool(tool_name, arguments)

    else:
        logger.error(f"Unsupported method: {request.method}")
        raise HTTPException(status_code=400, detail=f"Unsupported method: {request.method}")


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
