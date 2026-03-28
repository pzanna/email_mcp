"""MCP tool endpoint handlers."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional, Union
import json

from auth import verify_api_key
from tools.definitions import TOOL_SCHEMAS

# Attachment-specific exceptions
class AttachmentError(Exception):
    """Base exception for attachment operations."""
    pass

class AttachmentNotFoundError(AttachmentError):
    """Raised when attachment index is invalid or attachment not found."""
    pass

class AttachmentTooLargeError(AttachmentError):
    """Raised when attachment exceeds size limits."""
    pass

class InvalidAttachmentPathError(AttachmentError):
    """Raised when attachment path is invalid or outside workspace."""
    pass

router = APIRouter(prefix="/mcp", dependencies=[Depends(verify_api_key)])


class MCPToolCallRequest(BaseModel):
    """JSON-RPC 2.0 request format used by MCP."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[dict[str, Any]] = None


class MCPContentItem(BaseModel):
    """MCP content item."""
    type: str
    text: str


class MCPToolCallResponse(BaseModel):
    """MCP tools/call response format."""
    content: list[MCPContentItem]
    isError: bool = False


@router.get("/tools")
async def get_tools():
    """List available MCP tools."""
    return {"tools": TOOL_SCHEMAS}


@router.post("/call")
async def call_tool(request: MCPToolCallRequest) -> MCPToolCallResponse:
    """
    Execute an MCP tool by name.

    Request format:
    {
        "method": "tools/call",
        "params": {
            "name": "tool_name",
            "arguments": {...}
        }
    }

    Response format:
    {
        "content": [
            {
                "type": "text",
                "text": "<JSON output>"
            }
        ]
    }
    """
    if request.method != "tools/call":
        raise HTTPException(status_code=400, detail=f"Unsupported method: {request.method}")

    params = request.params or {}
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing tool name")

    # Use shared handler
    from .handlers import execute_tool
    return await execute_tool(tool_name, arguments)
