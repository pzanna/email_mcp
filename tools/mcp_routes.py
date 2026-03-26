"""MCP tool endpoint handlers."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import json

from auth import verify_api_key
from tools.definitions import TOOL_SCHEMAS

# Import tool implementations
from imap.read import list_folders, read_email, ReadEmailInput
from imap.search import search_emails, SearchEmailsInput
from imap.flags import mark_email, move_email, MarkEmailInput, MoveEmailInput
from smtp.client import send_email, reply_email, SendEmailInput, ReplyEmailInput

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

    # Dispatch to tool implementation
    try:
        if tool_name == "list_folders":
            result = await list_folders()

        elif tool_name == "search_emails":
            input_data = SearchEmailsInput(**arguments)
            result = await search_emails(input_data)

        elif tool_name == "read_email":
            input_data = ReadEmailInput(**arguments)
            result = await read_email(input_data)

        elif tool_name == "mark_email":
            input_data = MarkEmailInput(**arguments)
            result = await mark_email(input_data)

        elif tool_name == "move_email":
            input_data = MoveEmailInput(**arguments)
            result = await move_email(input_data)

        elif tool_name == "send_email":
            input_data = SendEmailInput(**arguments)
            result = await send_email(input_data)

        elif tool_name == "reply_email":
            input_data = ReplyEmailInput(**arguments)
            result = await reply_email(input_data)

        else:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

        # Convert result to JSON string
        result_json = result.model_dump_json()

        return MCPToolCallResponse(
            content=[
                MCPContentItem(type="text", text=result_json)
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        # Return error in MCP format
        error_data = {
            "error": str(type(e).__name__),
            "detail": str(e)
        }
        return MCPToolCallResponse(
            content=[
                MCPContentItem(type="text", text=json.dumps(error_data))
            ],
            isError=True
        )
