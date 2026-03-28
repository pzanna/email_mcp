"""Utility functions for attachment handling."""

import re
import logging
from pathlib import Path
from typing import Union
from tools.mcp_routes import InvalidAttachmentPathError

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing dangerous characters and path traversal.

    Args:
        filename: Original filename to sanitize

    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename or not filename.strip():
        return "unnamed"

    # Remove path traversal patterns completely
    filename = re.sub(r'\.\.+[/\\]*', '', filename)

    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)

    # Remove leading/trailing dots, spaces and underscores
    filename = filename.strip('. _')

    # Collapse multiple underscores
    filename = re.sub(r'_+', '_', filename)

    # If nothing left, use default
    if not filename:
        return "unnamed"

    return filename


def validate_workspace_path(file_path: str, workspace_dir: str) -> Path:
    """
    Validate that a file path is within the workspace directory.

    Args:
        file_path: Path to validate (relative or absolute)
        workspace_dir: Workspace root directory

    Returns:
        Resolved absolute Path object

    Raises:
        InvalidAttachmentPathError: If path is outside workspace
    """
    workspace_path = Path(workspace_dir).resolve()

    # Handle both relative and absolute paths
    if Path(file_path).is_absolute():
        resolved_path = Path(file_path).resolve()
    else:
        resolved_path = (workspace_path / file_path).resolve()

    # Check if resolved path is within workspace
    try:
        resolved_path.relative_to(workspace_path)
    except ValueError:
        raise InvalidAttachmentPathError(
            f"Path '{file_path}' is outside workspace directory '{workspace_dir}'"
        )

    return resolved_path


def ensure_directory_exists(directory: Union[str, Path]) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Directory path to create
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path}")


def get_mime_type_from_filename(filename: str) -> str:
    """
    Get MIME type from file extension.

    Args:
        filename: Filename to analyze

    Returns:
        MIME type string
    """
    import mimetypes

    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.2 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"