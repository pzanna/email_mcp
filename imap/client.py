"""IMAP client with connection pooling."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aioimaplib import IMAP4_SSL, IMAP4
from config import settings

logger = logging.getLogger(__name__)


class IMAPAuthError(Exception):
    """Raised when IMAP authentication fails."""
    pass


class IMAPConnectionError(Exception):
    """Raised when IMAP connection fails."""
    pass


class IMAPPool:
    """
    Connection pool for IMAP clients.

    Limits the number of concurrent IMAP connections using a semaphore.
    Each connection is created on-demand and closed after use.
    """

    def __init__(self, pool_size: int = 3):
        """
        Initialize the connection pool.

        Args:
            pool_size: Maximum number of concurrent connections
        """
        self._semaphore = asyncio.Semaphore(pool_size)
        self._pool_size = pool_size

    @asynccontextmanager
    async def acquire_connection(self) -> AsyncIterator[IMAP4_SSL | IMAP4]:
        """
        Acquire a connection from the pool.

        Yields:
            Connected and authenticated IMAP client

        Raises:
            IMAPAuthError: If authentication fails
            IMAPConnectionError: If connection fails
        """
        async with self._semaphore:
            client = None
            try:
                # Create IMAP client based on SSL setting
                if settings.IMAP_SSL:
                    client = IMAP4_SSL(
                        host=settings.IMAP_HOST,
                        port=settings.IMAP_PORT,
                        timeout=30,
                    )
                else:
                    client = IMAP4(
                        host=settings.IMAP_HOST,
                        port=settings.IMAP_PORT,
                        timeout=30,
                    )

                # Wait for server greeting
                await client.wait_hello_from_server()

                # Authenticate
                response = await client.login(
                    settings.IMAP_USER,
                    settings.IMAP_PASSWORD
                )

                # Check login response
                if response[0] != "OK":
                    error_msg = response[1][0].decode() if response[1] else "Authentication failed"
                    raise IMAPAuthError(f"IMAP_AUTH_FAILED: {error_msg}")

                logger.debug(f"IMAP connection established to {settings.IMAP_HOST}")

                yield client

            except IMAPAuthError:
                raise
            except Exception as e:
                logger.error(f"IMAP connection error: {e}")
                raise IMAPConnectionError(f"CONNECTION_TIMEOUT: {str(e)}")
            finally:
                # Clean up connection
                if client:
                    try:
                        await client.logout()
                    except Exception as e:
                        logger.warning(f"Error during IMAP logout: {e}")
                    try:
                        await client.close()
                    except Exception as e:
                        logger.warning(f"Error closing IMAP connection: {e}")


# Global connection pool instance
imap_pool = IMAPPool(pool_size=settings.IMAP_POOL_SIZE)
