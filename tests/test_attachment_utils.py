"""Tests for attachment utility functions."""

import pytest
from pathlib import Path
from utils.attachment_utils import (
    sanitize_filename, validate_workspace_path, ensure_directory_exists,
    get_mime_type_from_filename, format_file_size
)
from tools.mcp_routes import InvalidAttachmentPathError
import tempfile
import os

def test_sanitize_filename():
    """Test filename sanitization removes dangerous characters."""
    # Basic sanitization
    assert sanitize_filename("document.pdf") == "document.pdf"
    assert sanitize_filename("my document.pdf") == "my document.pdf"

    # Remove path traversal
    assert sanitize_filename("../../../etc/passwd") == "etc_passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\config") == "windows_system32_config"

    # Remove null bytes and control characters
    assert sanitize_filename("file\x00.pdf") == "file.pdf"
    assert sanitize_filename("file\n\r\t.pdf") == "file.pdf"

    # Handle empty or invalid names
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("...") == "unnamed"
    assert sanitize_filename("/") == "unnamed"

def test_validate_workspace_path():
    """Test workspace path validation."""
    with tempfile.TemporaryDirectory() as workspace:
        workspace_path = Path(workspace)

        # Valid paths within workspace
        valid_path = workspace_path / "attachments" / "email" / "test.pdf"
        validate_workspace_path(str(valid_path), workspace)  # Should not raise

        # Invalid path outside workspace
        with pytest.raises(InvalidAttachmentPathError):
            validate_workspace_path("/etc/passwd", workspace)

        # Invalid path with traversal
        with pytest.raises(InvalidAttachmentPathError):
            validate_workspace_path(str(workspace_path / ".." / "outside.pdf"), workspace)

def test_ensure_directory_exists():
    """Test directory creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_path = Path(temp_dir) / "deep" / "nested" / "directory"
        assert not test_path.exists()

        ensure_directory_exists(test_path)
        assert test_path.exists()
        assert test_path.is_dir()

        # Should not fail if directory already exists
        ensure_directory_exists(test_path)
        assert test_path.exists()

def test_get_mime_type_from_filename():
    """Test MIME type detection from filename."""
    # Common file types
    assert get_mime_type_from_filename("document.pdf") == "application/pdf"
    assert get_mime_type_from_filename("image.jpg") == "image/jpeg"
    assert get_mime_type_from_filename("image.png") == "image/png"
    assert get_mime_type_from_filename("document.txt") == "text/plain"
    assert get_mime_type_from_filename("data.json") == "application/json"

    # Unknown extension should return default
    assert get_mime_type_from_filename("file.totallyrandomext") == "application/octet-stream"

    # No extension should return default
    assert get_mime_type_from_filename("filename_no_ext") == "application/octet-stream"

def test_format_file_size():
    """Test file size formatting."""
    # Bytes
    assert format_file_size(0) == "0 B"
    assert format_file_size(500) == "500 B"
    assert format_file_size(1023) == "1023 B"

    # Kilobytes
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(1024 * 1023) == "1023.0 KB"

    # Megabytes
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(1024 * 1024 * 1.5) == "1.5 MB"
    assert format_file_size(1024 * 1024 * 1023) == "1023.0 MB"

    # Gigabytes
    assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_file_size(1024 * 1024 * 1024 * 2.5) == "2.5 GB"

def test_sanitize_filename_edge_cases():
    """Test additional edge cases for filename sanitization."""
    # Multiple path traversals
    assert sanitize_filename("....//....//file.pdf") == "file.pdf"

    # Mixed separators and traversals
    assert sanitize_filename("..\\../folder\\file.pdf") == "folder_file.pdf"

    # Only invalid characters
    assert sanitize_filename("///...\\\\") == "unnamed"

    # Whitespace handling
    assert sanitize_filename("  file name.pdf  ") == "file name.pdf"
    assert sanitize_filename("___file___") == "file"

def test_validate_workspace_path_edge_cases():
    """Test edge cases for workspace path validation."""
    with tempfile.TemporaryDirectory() as workspace:
        workspace_path = Path(workspace)

        # Test with relative paths
        relative_path = "attachments/file.pdf"
        result = validate_workspace_path(relative_path, workspace)
        assert result.is_absolute()
        assert workspace_path in result.parents

        # Test that returned path is resolved
        complex_path = workspace_path / "folder" / ".." / "file.pdf"
        result = validate_workspace_path(str(complex_path), workspace)
        assert result == workspace_path / "file.pdf"