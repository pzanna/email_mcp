"""
Email MCP Server - Main Application Entry Point

FastAPI application providing MCP-compliant email access via IMAP and SMTP.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from tools.mcp_routes import router as mcp_router

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
