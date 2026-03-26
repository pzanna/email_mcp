"""Authentication middleware for API key verification."""

from fastapi import Header, HTTPException, status
from config import settings


async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """
    Verify that the request includes a valid API key.

    Args:
        x_api_key: The API key from the X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: 401 if the API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    if x_api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return x_api_key
