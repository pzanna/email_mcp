"""
Email MCP Server - Main Application Entry Point

FastAPI application providing MCP-compliant email access via IMAP and SMTP.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from tools.mcp_routes import router as mcp_router, MCPToolCallRequest, MCPToolCallResponse
from auth import verify_api_key
from typing import Union, Any, Optional
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


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 success response envelope."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Any = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error response envelope."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    error: dict[str, Any]


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
async def mcp_tool_call(request: MCPToolCallRequest, api_key: str = Depends(verify_api_key)):
    """MCP endpoint - handles the full JSON-RPC 2.0 MCP session lifecycle."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Received MCP request: method='{request.method}', id={request.id}")

    req_id = request.id

    if request.method == "initialize":
        return JSONRPCResponse(
            id=req_id,
            result={
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "logging": {},
                },
                "serverInfo": {
                    "name": "email-mcp",
                    "version": "0.1.0",
                },
            },
        )

    elif request.method == "notifications/initialized":
        # Client notification after handshake — no response body per JSON-RPC 2.0
        return Response(status_code=202)

    elif request.method == "ping":
        return JSONRPCResponse(id=req_id, result={})

    elif request.method == "tools/list":
        from tools.definitions import TOOL_SCHEMAS
        return JSONRPCResponse(id=req_id, result={"tools": TOOL_SCHEMAS})

    elif request.method == "tools/call":
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return JSONRPCError(
                id=req_id,
                error={"code": -32602, "message": "Invalid params", "data": "Missing tool name"},
            )

        from tools.handlers import execute_tool
        tool_result = await execute_tool(tool_name, arguments)
        return JSONRPCResponse(id=req_id, result=tool_result.model_dump())

    else:
        logger.warning(f"Unknown MCP method: {request.method}")
        return JSONRPCError(
            id=req_id,
            error={"code": -32601, "message": f"Method not found: {request.method}"},
        )


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
