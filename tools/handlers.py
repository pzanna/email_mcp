"""Tool execution handlers shared between endpoints."""

import json
from typing import Any

# Import tool implementations
from imap.read import list_folders, read_email, ReadEmailInput
from imap.search import search_emails, SearchEmailsInput
from imap.flags import mark_email, move_email, MarkEmailInput, MoveEmailInput
from smtp.client import send_email, reply_email, SendEmailInput, ReplyEmailInput

from .mcp_routes import MCPContentItem, MCPToolCallResponse


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> MCPToolCallResponse:
    """
    Execute an MCP tool by name and return the response.

    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool

    Returns:
        MCPToolCallResponse with the tool result
    """
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
            # Return error in MCP format
            error_data = {
                "error": "UnknownTool",
                "detail": f"Unknown tool: {tool_name}"
            }
            return MCPToolCallResponse(
                content=[
                    MCPContentItem(type="text", text=json.dumps(error_data))
                ],
                isError=True
            )

        # Convert result to JSON string
        result_json = result.model_dump_json()

        return MCPToolCallResponse(
            content=[
                MCPContentItem(type="text", text=result_json)
            ]
        )

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