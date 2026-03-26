"""MCP tool endpoint handlers."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import json

from auth import verify_api_key
from tools.definitions import TOOL_SCHEMAS

router = APIRouter(prefix="/mcp", dependencies=[Depends(verify_api_key)])


class MCPToolCallRequest(BaseModel):
    """MCP tools/call request format."""
    method: str
    params: dict[str, Any]


class MCPContentItem(BaseModel):
    """MCP content item."""
    type: str
    text: str


class MCPToolCallResponse(BaseModel):
    """MCP tools/call response format."""
    content: list[MCPContentItem]
    isError: Optional[bool] = None


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

    tool_name = request.params.get("name")
    arguments = request.params.get("arguments", {})

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing tool name")

    # Use shared handler
    from .handlers import execute_tool
    return await execute_tool(tool_name, arguments)
