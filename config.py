"""Configuration management using pydantic-settings.

All configuration is loaded from environment variables via .env file.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # IMAP Configuration
    IMAP_HOST: str = Field(..., description="IMAP server hostname")
    IMAP_PORT: int = Field(..., description="IMAP server port")
    IMAP_USER: str = Field(..., description="IMAP username/email")
    IMAP_PASSWORD: str = Field(..., description="IMAP password")
    IMAP_SSL: bool = Field(..., description="Use SSL/TLS for IMAP connection")

    # SMTP Configuration
    SMTP_HOST: str = Field(..., description="SMTP server hostname")
    SMTP_PORT: int = Field(..., description="SMTP server port")
    SMTP_USER: str = Field(..., description="SMTP username/email")
    SMTP_PASSWORD: str = Field(..., description="SMTP password")
    SMTP_STARTTLS: bool = Field(..., description="Use STARTTLS for SMTP connection")

    # MCP Server Configuration
    MCP_API_KEY: str = Field(..., description="API key for authentication")
    MCP_HOST: str = Field(default="127.0.0.1", description="Host to bind server to")
    MCP_PORT: int = Field(default=8420, description="Port to bind server to")
    MCP_SERVER_NAME: str = Field(default="email-mcp", description="MCP server name")
    MCP_BASE_URL: str = Field(
        default="http://localhost:8420",
        description="Base URL for MCP server (e.g., http://192.168.2.3:8420)"
    )

    # Behavior Configuration
    DEFAULT_FROM_NAME: str = Field(
        default="",
        description="Default name to use in From field when sending emails"
    )
    MAX_SEARCH_RESULTS: int = Field(
        default=50,
        description="Maximum number of search results to return"
    )
    IMAP_POOL_SIZE: int = Field(
        default=3,
        description="Maximum number of concurrent IMAP connections"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields in .env
    )


# Singleton settings instance
settings = Settings()
